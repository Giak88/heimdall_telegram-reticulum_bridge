#!/usr/bin/env bash
# Heimdall - guided setup / installazione guidata (English / Italiano)
#
#   ./setup.sh                 first install, or a menu if Heimdall is already installed
#   ./setup.sh --lang it       choose the language (en | it) without asking
#   ./setup.sh --yes --token <bot token> --chat <chat id> --targets <hash,hash>
#                              unattended install (no questions)
#   ./setup.sh start|stop|restart|status|logs     manage the running bridge
#   ./setup.sh --uninstall     remove the service (asks before touching your data)
#
# Environment (advanced): HEIMDALL_HOME (data folder, default ~/.heimdall),
# HEIMDALL_UNIT_DIR (default /etc/systemd/system), HEIMDALL_VENV_FLAGS (e.g. --system-site-packages).
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${HEIMDALL_HOME:-$HOME/.heimdall}"
UNIT_DIR="${HEIMDALL_UNIT_DIR:-/etc/systemd/system}"
VENV="$DATA/venv"
CFG="$DATA/config.ini"
UNIT="heimdall"
VERSION="$(cat "$DIR/VERSION" 2>/dev/null || echo '?')"

LANGSEL="" ; YES=0 ; TOKEN="" ; CHAT="" ; TARGETS="" ; ACTION="" ; SKIP_TESTS=0

# ------------------------------------------------------------------ messages
declare -A M
m() { M["en.$1"]="$2"; M["it.$1"]="$3"; }

m title        "Heimdall %s - Telegram <-> Reticulum/LXMF bridge" "Heimdall %s - ponte Telegram <-> Reticulum/LXMF"
m root         "Do not run this as root: Heimdall must run as your normal user (it asks for sudo when needed)." "Non eseguirlo come root: Heimdall deve girare con il tuo utente normale (chiede sudo quando serve)."
m nosudo       "sudo is not available: the service cannot be installed." "sudo non è disponibile: non posso installare il service."
m nosystemd    "systemd not found: start the bridge yourself (see README)." "systemd non trovato: avvia il bridge a mano (vedi README)."
m step_deps    "Checking dependencies" "Controllo delle dipendenze"
m miss_pkgs    "Missing: %s" "Mancano: %s"
m ask_apt      "Install them now with apt-get?" "Li installo ora con apt-get?"
m no_apt       "No apt-get here: install them with your package manager and run ./setup.sh again." "Qui non c'è apt-get: installali con il tuo gestore di pacchetti e rilancia ./setup.sh."
m no_codec2    "Your ffmpeg has no libcodec2 (needed for LoRa voice notes). On Debian/Ubuntu the stock 'ffmpeg' package has it." "Il tuo ffmpeg non ha libcodec2 (serve per i vocali LoRa). Su Debian/Ubuntu il pacchetto 'ffmpeg' standard ce l'ha."
m no_opus      "Your ffmpeg has no libopus. Install a full ffmpeg build." "Il tuo ffmpeg non ha libopus. Installa una build completa di ffmpeg."
m deps_ok      "Dependencies OK (python3, ffmpeg with codec2+opus)" "Dipendenze OK (python3, ffmpeg con codec2+opus)"
m rnsd_ok      "Reticulum daemon (rnsd) is running" "Il demone Reticulum (rnsd) è attivo"
m rnsd_missing "rnsd is NOT running. Heimdall needs a running Reticulum instance (it never opens the radio itself): https://reticulum.network/manual/gettingstartedfast.html" "rnsd NON è attivo. Heimdall ha bisogno di un'istanza Reticulum attiva (non apre mai la radio da solo): https://reticulum.network/manual/gettingstartedfast.html"
m ask_cont     "Continue anyway?" "Continuo comunque?"
m step_py      "Python environment" "Ambiente Python"
m step_tests   "Self-test" "Autotest"
m tests_ok     "Self-test passed" "Autotest superato"
m tests_bad    "The self-test FAILED (output above). Installation continues, but media conversion may not work." "L'autotest è FALLITO (output sopra). L'installazione prosegue, ma la conversione dei media potrebbe non funzionare."
m step_cfg     "Configuration" "Configurazione"
m step_bot     "Telegram bot" "Bot Telegram"
m bot_how      "Create a bot with @BotFather on Telegram (/newbot) and paste its token here. Use a bot dedicated to Heimdall." "Crea un bot con @BotFather su Telegram (/newbot) e incolla qui il suo token. Usa un bot dedicato a Heimdall."
m ask_token    "Bot token" "Token del bot"
m token_bad    "Telegram refused the token: %s" "Telegram ha rifiutato il token: %s"
m token_ok     "Bot OK: @%s" "Bot OK: @%s"
m privacy_on   "Privacy mode is ON: in a group the bot would only see commands. In @BotFather: /setprivacy > choose the bot > Disable. Then remove and re-add the bot to the group." "La privacy mode è ATTIVA: in un gruppo il bot vedrebbe solo i comandi. In @BotFather: /setprivacy > scegli il bot > Disable. Poi togli e riaggiungi il bot al gruppo."
m step_chat    "Telegram group or channel" "Gruppo o canale Telegram"
m chat_how     "Add @%s to the group (or as an admin of the channel), then write any message there. I am listening for %s seconds..." "Aggiungi @%s al gruppo (o come amministratore del canale), poi scrivi un messaggio qualsiasi lì. Resto in ascolto per %s secondi..."
m chat_found   "Chats seen by the bot:" "Chat viste dal bot:"
m chat_pick    "Number of the chat to bridge (or type its id)" "Numero della chat da collegare (o scrivi il suo id)"
m chat_none    "No group seen. Type the chat id by hand (a negative number), or press Enter to try again" "Nessun gruppo visto. Scrivi a mano l'id della chat (numero negativo), oppure Invio per riprovare"
m chat_bad     "Not a valid chat id." "Id della chat non valido."
m chat_ok      "Bridged chat: %s" "Chat collegata: %s"
m step_tgt     "LXMF recipients" "Destinatari LXMF"
m tgt_how      "LXMF addresses that will receive the Telegram messages (32 hex characters; in Sideband the 'LXMF address'). Several separated by commas." "Indirizzi LXMF che riceveranno i messaggi Telegram (32 caratteri esadecimali; in Sideband l'\"indirizzo LXMF\"). Più indirizzi separati da virgola."
m ask_tgt      "Recipients" "Destinatari"
m tgt_bad      "Invalid address: %s" "Indirizzo non valido: %s"
m tgt_list     "Current recipients: %s" "Destinatari attuali: %s"
m none         "(none)" "(nessuno)"
m step_svc     "Service" "Servizio"
m svc_written  "Service installed: %s" "Service installato: %s"
m step_start   "Starting" "Avvio"
m wait_addr    "Waiting for the bridge to publish its address..." "Attendo che il bridge pubblichi il suo indirizzo..."
m done_title   "Done." "Fatto."
m done_addr    "Bridge LXMF address: %s" "Indirizzo LXMF del bridge: %s"
m done_next    "From Sideband/MeshChatX, write to that address: it is posted in the Telegram chat. /help there lists the commands." "Da Sideband/MeshChatX scrivi a quell'indirizzo: viene pubblicato nella chat Telegram. /aiuto lì elenca i comandi."
m done_noaddr  "The bridge has not published its address yet. Look at: ./setup.sh logs" "Il bridge non ha ancora pubblicato il suo indirizzo. Guarda: ./setup.sh logs"
m svc_status   "Service:" "Servizio:"
m svc_started  "Service started." "Servizio avviato."
m svc_stopped  "Service stopped." "Servizio fermato."
m not_installed "Heimdall is not installed yet: run ./setup.sh first." "Heimdall non è ancora installato: lancia prima ./setup.sh."
m menu_title   "Heimdall %s is installed. What do you want to do?" "Heimdall %s è installato. Cosa vuoi fare?"
m menu_1       " 1) Show status" " 1) Mostra lo stato"
m menu_2       " 2) Show the log (Ctrl+C to leave)" " 2) Mostra il log (Ctrl+C per uscire)"
m menu_3       " 3) Start" " 3) Avvia"
m menu_4       " 4) Stop" " 4) Ferma"
m menu_5       " 5) Restart" " 5) Riavvia"
m menu_6       " 6) Change the bot token" " 6) Cambia il token del bot"
m menu_7       " 7) Change the Telegram group/channel" " 7) Cambia il gruppo/canale Telegram"
m menu_8       " 8) Change the LXMF recipients" " 8) Cambia i destinatari LXMF"
m menu_9       " 9) Who can write from Reticulum (anyone / recipients only, /join)" " 9) Chi può scrivere da Reticulum (chiunque / solo destinatari, /entra)"
m menu_10      "10) Media quality (photos, voice notes)" "10) Qualità dei media (foto, vocali)"
m menu_11      "11) Change the language" "11) Cambia la lingua"
m menu_12      "12) Update (dependencies, service) from this folder" "12) Aggiorna (dipendenze, service) da questa cartella"
m menu_13      "13) Uninstall" "13) Disinstalla"
m menu_0       " 0) Quit" " 0) Esci"
m menu_ask     "Choice" "Scelta"
m ask_senders  "Who may post to Telegram by writing to the bridge? 1) anyone  2) only the recipients" "Chi può pubblicare su Telegram scrivendo al bridge? 1) chiunque  2) solo i destinatari"
m ask_subs     "Let any LXMF user receive the group with /join?" "Permetti a qualunque utente LXMF di ricevere il gruppo con /entra?"
m ask_qimg     "Photo quality: 1) low 320 px  2) medium 640 px  3) high 1280 px  4) original" "Qualità foto: 1) bassa 320 px  2) media 640 px  3) alta 1280 px  4) originale"
m ask_qaud     "Voice quality: 1) low Codec2  2) medium Opus 12k  3) high Opus 24k  4) original" "Qualità vocali: 1) bassa Codec2  2) media Opus 12k  3) alta Opus 24k  4) originale"
m saved        "Saved." "Salvato."
m lang_set     "Language set to %s." "Lingua impostata su %s."
m ask_unin     "Remove the Heimdall service?" "Rimuovo il service di Heimdall?"
m ask_data     "Also delete %s? It holds the bot token and the bridge identity (its LXMF address)." "Cancello anche %s? Contiene il token del bot e l'identità del bridge (il suo indirizzo LXMF)."
m unin_done    "Uninstalled. The program folder (%s) was left alone." "Disinstallato. La cartella del programma (%s) non è stata toccata."
m ask_lang     "Language / Lingua [en/it]" "Language / Lingua [en/it]"
m yes_hint     "[y/N]" "[s/N]"
m unknown_opt  "Unknown option: %s" "Opzione sconosciuta: %s"
m yes_needs    "--yes needs --token, --chat and --targets on a first install." "--yes richiede --token, --chat e --targets alla prima installazione."

say()  { local fmt="${M[$LANGSEL.$1]:-$1}"; shift; printf "$fmt\n" "$@"; }
step() { local fmt="${M[$LANGSEL.$1]}"; shift; printf "\n== $fmt\n" "$@"; }
warn() { local fmt="${M[$LANGSEL.$1]:-$1}"; shift; printf "!! $fmt\n" "$@" >&2; }
die()  { warn "$@"; exit 1; }
ask()  { local a; read -r -p "$(say "$1" "${@:2}"): " a; printf '%s' "$a"; }

# yes/no question; with --yes it is answered yes
confirm() {
  local ans
  [ "$YES" = 1 ] && return 0
  read -r -p "$(say "$1" "${@:2}") $(say yes_hint) " ans
  case "${ans,,}" in y|yes|s|si|sì) return 0 ;; *) return 1 ;; esac
}

# ------------------------------------------------------------------ args
while [ $# -gt 0 ]; do
  case "$1" in
    --lang)    LANGSEL="${2:-}"; shift 2 ;;
    --yes|-y)  YES=1; shift ;;
    --token)   TOKEN="${2:-}"; shift 2 ;;
    --chat)    CHAT="${2:-}"; shift 2 ;;
    --targets) TARGETS="${2:-}"; shift 2 ;;
    --skip-tests) SKIP_TESTS=1; shift ;;
    --uninstall) ACTION=uninstall; shift ;;
    start|stop|restart|status|logs) ACTION="$1"; shift ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) LANGSEL="${LANGSEL:-en}"; warn unknown_opt "$1"; exit 2 ;;
  esac
done

if [ -z "$LANGSEL" ] && [ -f "$CFG" ]; then
  LANGSEL="$(python3 "$DIR/tools/cfgtool.py" get "$CFG" bridge language 2>/dev/null | tr -d '[:space:]')"
fi
case "$LANGSEL" in en|it) ;; *)
  LANGSEL=en; case "${LANG:-}" in it*) LANGSEL=it ;; esac
  if [ "$YES" = 0 ] && [ -t 0 ] && [ -z "$ACTION" ]; then
    read -r -p "$(say ask_lang) " a; a="${a,,}"; { [ "$a" = en ] || [ "$a" = it ]; } && LANGSEL="$a"
  fi ;;
esac

# ------------------------------------------------------------------ helpers
HAVE_SYSTEMD=0; command -v systemctl >/dev/null 2>&1 && { [ -d /run/systemd/system ] || [ -n "${HEIMDALL_UNIT_DIR:-}" ]; } && HAVE_SYSTEMD=1
SUDO=""; [ "$(id -u)" != 0 ] && SUDO="sudo"
cfg_get() { python3 "$DIR/tools/cfgtool.py" get "$CFG" "$1" "$2"; }
cfg_set() { python3 "$DIR/tools/cfgtool.py" set "$CFG" "$1" "$2" "$3"; }
tg()      { "$VENV/bin/python" "$DIR/bridge/telegram.py" "$@"; }
is_installed() { [ -f "$CFG" ] && [ -x "$VENV/bin/python" ]; }
sysd() { $SUDO systemctl "$@"; }

# "a, <B>,c" -> "a, b, c" (lowercase, no <>); returns 1 and names the first invalid one
clean_targets() {
  local out=() h
  IFS=',' read -ra parts <<<"$1"
  for h in "${parts[@]}"; do
    h="${h//[<>[:space:]]/}"; h="${h,,}"
    [ -z "$h" ] && continue
    [[ "$h" =~ ^[0-9a-f]{32}$ ]] || { BAD="$h"; return 1; }
    out+=("$h")
  done
  [ ${#out[@]} -gt 0 ] || { BAD="(empty)"; return 1; }
  local IFS=','; CLEAN="${out[*]}"; CLEAN="${CLEAN//,/, }"
}

check_deps() {
  step step_deps
  local miss=() pkgs=()
  command -v ffmpeg >/dev/null || { miss+=(ffmpeg); pkgs+=(ffmpeg); }
  command -v python3 >/dev/null || { miss+=(python3); pkgs+=(python3); }
  python3 -c 'import venv, ensurepip' 2>/dev/null || { miss+=(python3-venv); pkgs+=(python3-venv); }
  if [ ${#miss[@]} -gt 0 ]; then
    say miss_pkgs "${miss[*]}"
    command -v apt-get >/dev/null || die no_apt
    confirm ask_apt || die no_apt
    $SUDO apt-get update && $SUDO apt-get install -y "${pkgs[@]}" || die miss_pkgs "${miss[*]}"
  fi
  local enc; enc="$(ffmpeg -hide_banner -encoders 2>/dev/null || true)"
  grep -q libcodec2 <<<"$enc" || die no_codec2
  grep -q libopus <<<"$enc" || die no_opus
  say deps_ok
  if { [ "$HAVE_SYSTEMD" = 1 ] && systemctl is-active --quiet rnsd 2>/dev/null; } || pgrep -x rnsd >/dev/null 2>&1 \
     || pgrep -f 'bin/rnsd' >/dev/null 2>&1; then
    say rnsd_ok
  else
    warn rnsd_missing
    confirm ask_cont || exit 1
  fi
}

setup_python() {
  step step_py
  mkdir -p "$DATA" && chmod 700 "$DATA"
  # shellcheck disable=SC2086
  [ -x "$VENV/bin/python" ] || python3 -m venv ${HEIMDALL_VENV_FLAGS:-} "$VENV" || die step_py
  "$VENV/bin/python" -m pip install -q --upgrade pip >/dev/null 2>&1 || true
  "$VENV/bin/python" -m pip install -q -r "$DIR/requirements.txt" || die step_py
  "$VENV/bin/python" -c 'import RNS, LXMF; print("RNS", RNS.__version__, "- LXMF", LXMF.__version__)' || die step_py
}

run_selftest() {
  [ "$SKIP_TESTS" = 1 ] && return 0
  step step_tests
  local d; d="$(mktemp -d)"
  if "$VENV/bin/python" "$DIR/tests/make_media.py" "$d" && "$VENV/bin/python" "$DIR/tests/test_i18n.py" \
     && "$VENV/bin/python" "$DIR/tests/test_core.py" "$d" "$LANGSEL" | tail -1; then
    say tests_ok
  else
    warn tests_bad
  fi
  rm -rf "$d"
}

ensure_config() {
  if [ ! -f "$CFG" ]; then
    local ex="$DIR/config.example.ini"; [ "$LANGSEL" = it ] && ex="$DIR/config.example.it.ini"
    cp "$ex" "$CFG"; chmod 600 "$CFG"
    [ "$DATA" = "$HOME/.heimdall" ] || cfg_set bridge dir "$DATA"
  fi
  cfg_set bridge language "$LANGSEL"
}

# ---- token: validated with getMe; sets BOT_USER
set_token() {
  step step_bot
  local tok="$TOKEN" out
  while :; do
    if [ -z "$tok" ]; then
      [ "$YES" = 1 ] && die yes_needs
      say bot_how; tok="$(ask ask_token)"; tok="${tok//[[:space:]]/}"
      [ -n "$tok" ] || continue
    fi
    if out="$(tg getme "$tok" 2>&1)"; then break; fi
    warn token_bad "${out#ERROR }"
    [ "$YES" = 1 ] && exit 1
    tok=""
  done
  BOT_USER="${out%% *}"
  say token_ok "$BOT_USER"
  [ "${out##* }" = yes ] || warn privacy_on
  cfg_set telegram token "$tok"
}

# ---- chat: from --chat, or discovered by listening to the bot's updates
set_chat() {
  step step_chat
  local id="$CHAT" tok lines=() i pick
  tok="$(cfg_get telegram token)"
  [ -n "${BOT_USER:-}" ] || BOT_USER="$(tg getme "$tok" 2>/dev/null | cut -d' ' -f1)"
  while [ -z "$id" ]; do
    [ "$YES" = 1 ] && die yes_needs
    local secs="${HEIMDALL_DISCOVER_SECS:-90}"
    say chat_how "$BOT_USER" "$secs"
    mapfile -t lines < <(tg discover "$tok" "$secs" 2>/dev/null)
    if [ ${#lines[@]} -gt 0 ]; then
      say chat_found
      for i in "${!lines[@]}"; do IFS=$'\t' read -r cid ctype ctitle <<<"${lines[$i]}"; printf '  %d) %s  [%s]  %s\n' $((i + 1)) "$ctitle" "$ctype" "$cid"; done
      pick="$(ask chat_pick)"
      if [[ "$pick" =~ ^[0-9]+$ ]] && [ "$pick" -ge 1 ] && [ "$pick" -le ${#lines[@]} ]; then
        id="$(cut -f1 <<<"${lines[$((pick - 1))]}")"
      else
        id="$pick"
      fi
    else
      id="$(ask chat_none)"
    fi
    if [ -n "$id" ] && ! [[ "$id" =~ ^-?[0-9]+$ ]]; then say chat_bad; id=""; fi
  done
  [[ "$id" =~ ^-?[0-9]+$ ]] || die chat_bad
  cfg_set telegram chat_id "$id"
  say chat_ok "$id"
}

set_targets() {
  step step_tgt
  local cur v="$TARGETS"
  cur="$(cfg_get lxmf targets)"
  say tgt_list "${cur:-$(say none)}"
  while :; do
    if [ -z "$v" ]; then
      [ "$YES" = 1 ] && die yes_needs
      say tgt_how; v="$(ask ask_tgt)"
      [ -z "$v" ] && [ -n "$cur" ] && return 0
    fi
    if clean_targets "$v"; then break; fi
    warn tgt_bad "$BAD"; [ "$YES" = 1 ] && exit 1; v=""
  done
  cfg_set lxmf targets "$CLEAN"
  say tgt_list "$CLEAN"
}

install_service() {
  step step_svc
  [ "$HAVE_SYSTEMD" = 1 ] || { warn nosystemd; return 0; }
  [ -z "$SUDO" ] || command -v sudo >/dev/null || die nosudo
  local rnsd_unit="" rnsd_req=""
  if systemctl list-unit-files rnsd.service 2>/dev/null | grep -q '^rnsd\.service' || [ -f "$UNIT_DIR/rnsd.service" ]; then
    rnsd_unit="rnsd.service"; rnsd_req="Requires=rnsd.service"
  fi
  sed -e "s#@USER@#$(id -un)#g" -e "s#@DIR@#$DIR#g" -e "s#@DATA@#$DATA#g" \
      -e "s#@RNSD_UNIT@#$rnsd_unit#g" -e "s#@RNSD_REQUIRES@#$rnsd_req#g" \
      "$DIR/systemd/$UNIT.service.in" | $SUDO tee "$UNIT_DIR/$UNIT.service" >/dev/null || die step_svc
  sysd daemon-reload
  sysd enable "$UNIT" >/dev/null 2>&1
  say svc_written "$UNIT_DIR/$UNIT.service"
}

restart() { [ "$HAVE_SYSTEMD" = 1 ] && sysd restart "$UNIT"; }

final_summary() {
  local addr="" i
  echo; say wait_addr
  for i in $(seq 1 "${HEIMDALL_ADDR_WAIT:-40}"); do [ -s "$DATA/address.txt" ] && break; sleep 1; done
  addr="$(cat "$DATA/address.txt" 2>/dev/null || true)"
  say done_title
  if [ -n "$addr" ]; then say done_addr "$addr"; say done_next; else say done_noaddr; fi
}

do_install() {
  check_deps; setup_python; run_selftest
  step step_cfg; ensure_config
  [ -n "$(cfg_get telegram token)" ] && [ -z "$TOKEN" ] || set_token
  [ -n "$(cfg_get telegram chat_id)" ] && [ -z "$CHAT" ] || set_chat
  [ -n "$(cfg_get lxmf targets)" ] && [ -z "$TARGETS" ] || set_targets
  install_service
  step step_start; restart
  final_summary
}

do_update() { check_deps; setup_python; run_selftest; ensure_config; install_service; restart; final_summary; }

do_uninstall() {
  confirm ask_unin || exit 0
  if [ "$HAVE_SYSTEMD" = 1 ]; then
    sysd disable --now "$UNIT" 2>/dev/null
    $SUDO rm -f "$UNIT_DIR/$UNIT.service"
    sysd daemon-reload
  fi
  if [ "$YES" = 0 ] && confirm ask_data "$DATA"; then rm -rf "$DATA"; fi
  say unin_done "$DIR"
}

show_status() {
  say svc_status; sysd --no-pager status "$UNIT" 2>&1 | sed -n '1,12p'
  [ -s "$DATA/address.txt" ] && say done_addr "$(cat "$DATA/address.txt")"
  say chat_ok "$(cfg_get telegram chat_id)"
  local cur; cur="$(cfg_get lxmf targets)"; say tgt_list "${cur:-$(say none)}"
}

service_cmd() {
  [ "$HAVE_SYSTEMD" = 1 ] || die nosystemd
  [ -f "$UNIT_DIR/$UNIT.service" ] || die not_installed
  case "$1" in
    start|restart) sysd restart "$UNIT" && say svc_started ;;
    stop)          sysd stop "$UNIT" && say svc_stopped ;;
    status)        show_status ;;
    logs)          $SUDO journalctl -u "$UNIT" -f -n 40 ;;
  esac
}

level_of() { case "$1" in 1) echo low ;; 2) echo medium ;; 3) echo high ;; 4) echo original ;; esac; }

menu() {
  while :; do
    echo; say menu_title "$VERSION"
    for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 0; do say "menu_$i"; done
    read -r -p "$(say menu_ask): " c
    case "$c" in
      1) show_status ;;
      2) service_cmd logs ;;
      3) service_cmd start ;;
      4) service_cmd stop ;;
      5) service_cmd restart ;;
      6) TOKEN=""; set_token; restart ;;
      7) CHAT=""; sysd stop "$UNIT" 2>/dev/null   # the bridge would consume the updates we listen to
         set_chat; restart ;;
      8) TARGETS=""; set_targets; restart ;;
      9) local s; read -r -p "$(say ask_senders) " s
         case "$s" in 1) cfg_set lxmf senders anyone ;; 2) cfg_set lxmf senders targets ;; esac
         if confirm ask_subs; then cfg_set lxmf subscriptions yes; else cfg_set lxmf subscriptions no; fi
         restart; say saved ;;
      10) local q; read -r -p "$(say ask_qimg) " q; [ -n "$(level_of "$q")" ] && cfg_set limits quality_img "$(level_of "$q")"
          read -r -p "$(say ask_qaud) " q; [ -n "$(level_of "$q")" ] && cfg_set limits quality_audio "$(level_of "$q")"
          restart; say saved ;;
      11) local l; read -r -p "$(say ask_lang) " l; l="${l,,}"
          if [ "$l" = en ] || [ "$l" = it ]; then LANGSEL="$l"; cfg_set bridge language "$l"; restart; say lang_set "$l"; fi ;;
      12) do_update ;;
      13) do_uninstall; return ;;
      0|q|"") return ;;
    esac
  done
}

# ------------------------------------------------------------------ main
[ "$(id -u)" != 0 ] || [ -n "${HEIMDALL_ALLOW_ROOT:-}" ] || { LANGSEL="${LANGSEL:-en}"; die root; }
case "$ACTION" in
  uninstall) do_uninstall; exit 0 ;;
  start|stop|restart|status|logs) service_cmd "$ACTION"; exit $? ;;
esac
say title "$VERSION"
if is_installed && [ "$YES" = 0 ] && [ -z "$TOKEN$CHAT$TARGETS" ] && [ -t 0 ]; then
  menu
else
  do_install
fi
