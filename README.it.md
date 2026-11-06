# Heimdall

[English](README.md) · **Italiano**

Un ponte tra un **gruppo o canale Telegram** e **Reticulum / LXMF**. Heimdall ha un suo indirizzo LXMF: quello che chiunque scrive a quell'indirizzo da Sideband o MeshChatX viene pubblicato nella chat Telegram con il nome del mittente, e quello che si scrive nella chat Telegram arriva agli indirizzi LXMF che scegli tu — via LoRa, TCP o qualunque cosa compone la tua rete Reticulum. Foto, vocali e file viaggiano in entrambe le direzioni, compressi per stare in un link radio.

> **Stato: alpha (`alpha0.1`).** Provato end to end contro un vero `rnsd` e una Bot API Telegram simulata. Progetto gemello di [Bifrost](https://github.com/Giak88/bifrost_whatsapp-reticulum_bridge) (WhatsApp ⇄ Reticulum).

```
Gruppo/canale Telegram ── Bot API ── Heimdall (Python) ── rnsd (shared instance) ── RNode / TCP / ...
```

Heimdall **non apre mai la tua radio**: è un client della shared instance di `rnsd`, come Sideband o MeshChatX, quindi possono girare tutti sullo stesso nodo. Solo Python: niente Node.js.

## Funzioni

- **Telegram → LXMF**: i messaggi della chat collegata arrivano a ogni destinatario LXMF configurato come `Nome: testo`
- **LXMF → Telegram**: chiunque (o solo i destinatari, scegli tu) scrive all'indirizzo del bridge e il messaggio viene pubblicato come **Nome**: testo, con il nome che il mittente annuncia su Reticulum
- Le foto diventano WebP (preset di Sideband), i vocali Codec2 oppure Opus; qualità configurabile
- **Conferma per i media grossi**: sopra una soglia (32 KB) i destinatari ricevono un avviso con dimensione e tempo di trasmissione, e lo scaricano con `/scarica N`. Video e file grossi vengono scaricati da Telegram solo quando qualcuno li chiede
- `/entra` / `/esci` facoltativi per far iscrivere da soli gli utenti LXMF; eco facoltativo tra utenti LXMF
- Limite di messaggi per mittente, lista di blocco, nomi fissi per gli indirizzi
- Migrazione gruppo → supergruppo seguita in automatico; canali supportati (bot amministratore)
- Italiano e inglese: risposte del bot, log, comandi (`/scarica` = `/download`, ...), installer
- Installer guidato `setup.sh` con menu di manutenzione

## Requisiti

- Una macchina Linux con **systemd** (sviluppato su Debian 13)
- **Reticulum** (`rnsd`) installato e attivo con radio/rete configurate
- Python 3 con `venv`, **ffmpeg compilato con libcodec2 e libopus** (il pacchetto `ffmpeg` standard di Debian/Ubuntu li ha entrambi)
- Un **bot Telegram dedicato a Heimdall** (crealo con [@BotFather](https://t.me/BotFather), `/newbot`)
- Per un **gruppo**: disattiva la privacy mode del bot (@BotFather → `/setprivacy` → Disable), altrimenti vede solo i comandi. Fallo *prima* di aggiungere il bot al gruppo (o toglilo e riaggiungilo)
- Per un **canale**: aggiungi il bot come amministratore con il permesso di pubblicare

## Avvio rapido

```bash
git clone https://github.com/Giak88/heimdall_telegram-reticulum_bridge.git
cd heimdall_telegram-reticulum_bridge
./setup.sh                 # chiede la lingua, poi ti guida in tutto
```

L'installer controlla le dipendenze (e propone di installarle), controlla `rnsd`, crea l'ambiente Python in `~/.heimdall/venv`, esegue un autotest, poi chiede:

1. il **token del bot** (verificato con Telegram; avvisa se la privacy mode è attiva)
2. la **chat**: aggiungi il bot al gruppo e scrivi un messaggio qualsiasi lì — l'installer lo vede e te lo elenca, tu lo scegli (o scrivi il suo id)
3. i **destinatari LXMF**: gli indirizzi che riceveranno i messaggi Telegram (32 caratteri esadecimali ciascuno, separati da virgola)

poi installa e avvia il service `heimdall` e stampa **l'indirizzo LXMF del bridge**. Scrivigli da Sideband: compare nella chat Telegram.

Non interattivo: `./setup.sh --lang it --yes --token <token> --chat <id> --targets <hash>[,<hash>...]`.

## Avviare, fermare, riavviare

```bash
./setup.sh start        # (ri)avvia
./setup.sh stop
./setup.sh restart      # dopo aver modificato config.ini
./setup.sh status       # stato del service, indirizzo del bridge, chat, destinatari
./setup.sh logs         # segue il log (Ctrl+C per uscire)
./setup.sh              # menu: quanto sopra, più token, chat, destinatari, chi può scrivere,
                        # qualità dei media, lingua, aggiornamento, disinstallazione
```

Direttamente con systemd: `sudo systemctl restart|stop|start heimdall`, `sudo systemctl disable --now heimdall` per non farlo partire al boot.

## Uso da Reticulum

Scrivi all'indirizzo del bridge come a qualunque contatto LXMF. Testo, foto, vocali e file vengono pubblicati nella chat Telegram. Comandi:

| Comando | Cosa fa |
|---|---|
| `/scarica N` | ricevi il media numero N trattenuto perché troppo grande (solo i destinatari) |
| `/stato` | versione, stato di Telegram, chat, numero di destinatari, media trattenuti |
| `/entra`, `/esci` | ricevi qui la chat Telegram / smetti (solo se `subscriptions = yes`) |
| `/aiuto` | l'elenco |

Alias inglesi: `/download`, `/status`, `/join`, `/leave`, `/help`.

Su Telegram i mittenti compaiono con il nome che annunciano (il "display name" di Sideband), oppure `<primi 8 hex>` se il bridge non ha ancora ricevuto il loro annuncio. Nomi fissi si impostano in `[names]`.

## Media

| Telegram → LXMF | |
|---|---|
| foto | WebP a `quality_img`: `low` 320 px q22 · `medium` 640 px q66 · `high` 1280 px q75 · `original` |
| vocale / audio | `quality_audio`: `low` Codec2 2400 · `medium` Opus 12 kbps · `high` Opus 24 kbps · `original` |
| video, GIF, documento | invariati, scaricati da Telegram solo quando qualcuno manda `/scarica N` |
| posizione, contatto, sondaggio, sticker | come testo (posizioni con link OpenStreetMap) |

Se una foto o un vocale convertiti superano `max_file_mb`, scendono da soli di livello. Ciò che dopo la conversione supera `confirm_threshold_kb` (32) viene trattenuto per `/scarica N`; sopra `max_file_mb` (0,9: i router LXMF di serie rifiutano oltre 1000 KB) non si può consegnare. I bot Telegram scaricano al massimo 20 MB.

| LXMF → Telegram | |
|---|---|
| immagine | foto (JPEG) |
| audio (Codec2 o Opus) | vocale |
| file | video se è un video, altrimenti documento (limite dei bot Telegram: 50 MB) |

Heimdall accetta messaggi LXMF fino a `max_receive_mb` (10). Su LoRa mandare megabyte richiede molto tempo: comprimi in Sideband quando invii.

## Configurazione

`~/.heimdall/config.ini` (modello commentato: [`config.example.it.ini`](config.example.it.ini)). Dopo ogni modifica: `./setup.sh restart`.

| Chiave | Default | Significato |
|---|---|---|
| `[bridge] language` | `en` | `en` o `it` |
| `max_receive_mb` | 10 | messaggio LXMF più grande accettato |
| `[telegram] token`, `chat_id` | – | il bot e la chat collegata |
| `[lxmf] targets` | – | indirizzi che ricevono la chat Telegram |
| `senders` | `anyone` | chi può pubblicare: `anyone` o `targets` |
| `subscriptions` | `no` | consente `/entra` |
| `echo` | `no` | ripete il messaggio di un utente LXMF agli altri destinatari LXMF |
| `blocked` | – | indirizzi sempre ignorati |
| `[limits] confirm_threshold_kb` | 32 | trattiene i media sopra questa dimensione |
| `max_file_mb` | 0.9 | sopra non consegna mai |
| `quality_img`, `quality_audio` | `low` | vedi Media |
| `rate_per_min` | 10 | limite per mittente (0 = nessuno) |
| `[names] <hash> = Nome` | – | nomi fissi |

## Log e risoluzione dei problemi

`./setup.sh logs` (oppure `sudo journalctl -u heimdall -f`). L'indirizzo del bridge è anche in `~/.heimdall/address.txt`.

| Sintomo | Causa probabile |
|---|---|
| Dal gruppo non arriva nulla | privacy mode ancora attiva: @BotFather → `/setprivacy` → Disable, poi togli e riaggiungi il bot |
| `un altro programma sta leggendo gli aggiornamenti di questo bot` | il token è usato altrove (webhook o un'altra copia): usa un bot dedicato |
| La pubblicazione fallisce con `Forbidden` / `not enough rights` | in un canale il bot deve essere amministratore con permesso di pubblicare |
| Nel log un messaggio risulta "perso" | il destinatario non era raggiungibile: 4 tentativi a 30 s, poi il propagation node se configurato |
| Mittente mostrato come `<abcd1234>` | il bridge non ha ancora ricevuto il suo annuncio; oppure imposta un nome in `[names]` |
| Journal pieno di righe `Pathing` | `loglevel` in `~/.reticulum/config` troppo alto (metti 4) |

## Limiti noti

- Una chat collegata per installazione (un router LXMF gestisce una sola identità di consegna). Per una seconda chat, una seconda copia con un altro `HEIMDALL_HOME`.
- Risposte, modifiche, cancellazioni e reazioni su Telegram non vengono riportate; i topic (thread dei forum) non sono distinti.
- I media trattenuti per `/scarica` scadono dopo `pending_ttl_h` (24 h).
- Il fallback via propagation node è implementato ma non provato sul campo.

## Note di sicurezza

- Il token del bot sta in `~/.heimdall/config.ini` (permessi 600): chi lo ha controlla il bot.
- Con `senders = anyone` chiunque sulla rete Reticulum può pubblicare nella tua chat Telegram. Usa `targets`, `blocked` e `rate_per_min` di conseguenza.
- Le chat dei bot Telegram non sono cifrate end-to-end, e la macchina del bridge vede tutto in chiaro.

## Sviluppo

```bash
tests/run_tests.sh              # catalogo, config, core (EN e IT); servono rns + lxmf + Pillow + ffmpeg
tests/e2e.sh python3 it         # rnsd privato + bridge vero + Bot API Telegram finta + client LXMF finto
tests/test_setup.sh             # setup.sh contro sudo/systemctl finti e la Bot API finta
```

## Crediti

Idea e prove sul campo di [Giak88](https://github.com/Giak88). Progettato e scritto con Claude (Anthropic).
Costruito su [Reticulum](https://reticulum.network) e [LXMF](https://github.com/markqvist/LXMF) di Mark Qvist e sulla [Bot API di Telegram](https://core.telegram.org/bots/api), seguendo le convenzioni sui media di [Sideband](https://github.com/markqvist/Sideband). Non affiliato con Telegram.

## Licenza

MIT, vedi [LICENSE](LICENSE).
