"""Heimdall messages in English and Italian / Messaggi di Heimdall in inglese e italiano.

t = make_t("it"); t("help"); t("pending_notice", head="Ann", ...)
A missing translation falls back to English.
"""

LANGS = ("en", "it")

MSG = {
    # ---------------------------------------------------------------- commands (LXMF side)
    "help": {
        "en": """Heimdall: this address is bridged to a Telegram {where}.
Whatever you write here is posted there with your name; what is written there arrives here.
/download N - fetch a media file that was held back because of its size
/status - bridge status
/join, /leave - receive the {where}'s messages here (if allowed)
/help - this text""",
        "it": """Heimdall: questo indirizzo è collegato a un {where} Telegram.
Quello che scrivi qui viene pubblicato lì con il tuo nome; quello che si scrive lì arriva qui.
/scarica N - ricevi un media trattenuto perché troppo grande
/stato - stato del bridge
/entra, /esci - ricevi qui i messaggi del {where} (se consentito)
/aiuto - questo testo""",
    },
    "where_group": {"en": "group", "it": "gruppo"},
    "where_channel": {"en": "channel", "it": "canale"},
    "status": {
        "en": "{version}\nTelegram: {tg} ({chat})\nRecipients: {targets} fixed + {subs} subscribed\nHeld media: {pending}",
        "it": "{version}\nTelegram: {tg} ({chat})\nDestinatari: {targets} fissi + {subs} iscritti\nMedia trattenuti: {pending}",
    },
    "tg_ok": {"en": "connected", "it": "connesso"},
    "tg_down": {"en": "not reachable", "it": "non raggiungibile"},
    "tg_unknown": {"en": "starting", "it": "in avvio"},
    "unknown_command": {
        "en": "Unknown command: {cmd}. /help for the list.",
        "it": "Comando sconosciuto: {cmd}. /aiuto per l'elenco.",
    },
    "download_none": {
        "en": "Nothing held back with number {n} (it may have expired).",
        "it": "Niente in attesa con il numero {n} (forse è scaduto).",
    },
    "download_usage": {"en": "Usage: /download N", "it": "Uso: /scarica N"},
    "download_failed": {"en": "⚠️ Could not fetch the file: {err}", "it": "⚠️ Non riesco a scaricare il file: {err}"},
    "join_ok": {
        "en": "You will receive the Telegram {where}'s messages here. /leave to stop.",
        "it": "Riceverai qui i messaggi del {where} Telegram. /esci per smettere.",
    },
    "join_already": {"en": "You are already receiving them.", "it": "Li ricevi già."},
    "join_fixed": {
        "en": "You are a fixed recipient (set in the config): /leave cannot remove you.",
        "it": "Sei un destinatario fisso (impostato nella config): /esci non può toglierti.",
    },
    "join_closed": {
        "en": "Subscriptions are closed on this bridge.",
        "it": "Le iscrizioni su questo bridge sono chiuse.",
    },
    "leave_ok": {"en": "Done, you will no longer receive them.", "it": "Fatto, non li riceverai più."},
    "leave_none": {"en": "You were not subscribed.", "it": "Non eri iscritto."},
    "rate_limited": {
        "en": "⚠️ Too many messages: at most {n} per minute. The last one was not posted.",
        "it": "⚠️ Troppi messaggi: al massimo {n} al minuto. L'ultimo non è stato pubblicato.",
    },
    "not_allowed": {
        "en": "This bridge only accepts messages from its recipients.",
        "it": "Questo bridge accetta messaggi solo dai suoi destinatari.",
    },
    "tg_send_failed": {
        "en": "⚠️ Not posted on Telegram ({what}): {err}",
        "it": "⚠️ Non pubblicato su Telegram ({what}): {err}",
    },
    "tg_too_big": {
        "en": "⚠️ {name} is {size}: Telegram bots can upload at most 50 MB.",
        "it": "⚠️ {name} pesa {size}: i bot Telegram caricano al massimo 50 MB.",
    },
    "empty": {"en": "Empty message, nothing posted.", "it": "Messaggio vuoto, niente da pubblicare."},
    "what_text": {"en": "text", "it": "testo"},
    "what_image": {"en": "image", "it": "immagine"},
    "what_voice": {"en": "voice note", "it": "vocale"},
    "what_file": {"en": "file {name}", "it": "file {name}"},

    # ---------------------------------------------------------------- Telegram -> LXMF
    "kind_photo": {"en": "photo", "it": "foto"},
    "kind_voice": {"en": "voice note", "it": "vocale"},
    "kind_audio": {"en": "audio", "it": "audio"},
    "kind_video": {"en": "video", "it": "video"},
    "kind_video_note": {"en": "video message", "it": "videomessaggio"},
    "kind_animation": {"en": "GIF", "it": "GIF"},
    "kind_document": {"en": "file", "it": "file"},
    "label_image": {"en": "photo {level}", "it": "foto {level}"},
    "label_voice": {"en": "voice note {secs} s {level}", "it": "vocale {secs} s {level}"},
    "reduced_note": {"en": " [reduced to {level}: too large]", "it": " [ridotta a {level}: troppo grande]"},
    "media_pending": {
        "en": "{head}: {icon} {label}, {size} ({eta} over LoRa). /download {pid} to receive it. {caption}",
        "it": "{head}: {icon} {label}, {size} ({eta} su LoRa). /scarica {pid} per riceverlo. {caption}",
    },
    "media_too_big": {
        "en": "{head}: {icon} {label}, {size}: too large for Reticulum. {caption}",
        "it": "{head}: {icon} {label}, {size}: troppo grande per Reticulum. {caption}",
    },
    "media_unavailable": {
        "en": "{head}: {icon} {label} not available ({err}). {caption}",
        "it": "{head}: {icon} {label} non disponibile ({err}). {caption}",
    },
    "sticker": {"en": "sticker", "it": "sticker"},
    "location": {"en": "location", "it": "posizione"},
    "contact": {"en": "contact", "it": "contatto"},
    "poll": {"en": "poll", "it": "sondaggio"},
    "unsupported": {"en": "[{kind}: not supported]", "it": "[{kind}: non supportato]"},
    "chat_migrated": {
        "en": "The Telegram group became a supergroup: new id {new}",
        "it": "Il gruppo Telegram è diventato un supergruppo: nuovo id {new}",
    },
    "level_low": {"en": "low", "it": "basso"},
    "level_medium": {"en": "medium", "it": "medio"},
    "level_high": {"en": "high", "it": "alto"},
    "level_original": {"en": "original", "it": "originale"},

    # ---------------------------------------------------------------- logs
    "cfg_not_found": {"en": "Config not found: {path}", "it": "Config non trovata: {path}"},
    "token_missing": {
        "en": "Set [telegram] token and chat_id in the config (./setup.sh does it for you)",
        "it": "Imposta [telegram] token e chat_id nella config (./setup.sh lo fa per te)",
    },
    "target_invalid": {
        "en": "Invalid LXMF address '{value}': it must be 32 hexadecimal characters (edit config.ini)",
        "it": "Indirizzo LXMF non valido '{value}': servono 32 caratteri esadecimali (modifica config.ini)",
    },
    "starting": {"en": "Heimdall {version} starting", "it": "Heimdall {version} in avvio"},
    "not_shared": {
        "en": "WARNING: not attached to rnsd, running as a standalone Reticulum instance",
        "it": "ATTENZIONE: non sono agganciato a rnsd, sto girando come istanza autonoma",
    },
    "address_log": {"en": "Bridge LXMF address: {addr}", "it": "Indirizzo LXMF del bridge: {addr}"},
    "tg_connected": {"en": "Telegram: logged in as @{user}", "it": "Telegram: collegato come @{user}"},
    "tg_error": {"en": "Telegram: {err}", "it": "Telegram: {err}"},
    "tg_conflict": {
        "en": "Telegram: another program is reading this bot's updates (webhook or second copy). Use a dedicated bot.",
        "it": "Telegram: un altro programma sta leggendo gli aggiornamenti di questo bot (webhook o seconda copia). Usa un bot dedicato.",
    },
    "tg_privacy": {
        "en": "Telegram: privacy mode is ON, the bot only sees commands in groups. BotFather > /setprivacy > Disable",
        "it": "Telegram: la privacy mode è ATTIVA, nei gruppi il bot vede solo i comandi. BotFather > /setprivacy > Disable",
    },
    "ignore_chat": {"en": "Ignoring Telegram chat {id} ({title})", "it": "Ignoro la chat Telegram {id} ({title})"},
    "ignore_sender": {"en": "Ignoring message from {src}: {why}", "it": "Ignoro messaggio da {src}: {why}"},
    "why_blocked": {"en": "blocked", "it": "bloccato"},
    "why_not_target": {"en": "not a recipient", "it": "non è un destinatario"},
    "posted_log": {"en": "LXMF {src} -> Telegram: {what}", "it": "LXMF {src} -> Telegram: {what}"},
    "queued_log": {
        "en": "Queued for {dest}: {chars} characters, fields {fields}",
        "it": "In coda per {dest}: {chars} caratteri, campi {fields}",
    },
    "dropped_log": {
        "en": "Message for {dest} dropped: recipient unknown for an hour",
        "it": "Messaggio per {dest} scartato: destinatario sconosciuto da un'ora",
    },
    "delivered_log": {"en": "Delivered to {dest} (attempt {n})", "it": "Consegnato a {dest} (tentativo {n})"},
    "retry_log": {
        "en": "Delivery to {dest} failed (attempt {n}/{max}), retrying in 30 s",
        "it": "Consegna a {dest} fallita (tentativo {n}/{max}), riprovo tra 30 s",
    },
    "propagation_log": {
        "en": "Direct delivery to {dest} failed, trying the propagation node",
        "it": "Consegna diretta a {dest} fallita, provo via propagation node",
    },
    "lost_log": {"en": "Delivery to {dest} failed for good: message lost", "it": "Consegna a {dest} fallita definitivamente: messaggio perso"},
    "internal_error": {"en": "⚠️ Internal error: {err}", "it": "⚠️ Errore interno: {err}"},
    "state_unreadable": {
        "en": "state file unreadable, starting from scratch: {err}",
        "it": "stato illeggibile, riparto da zero: {err}",
    },
}

LEVEL_ALIASES = {
    "low": "low", "basso": "low", "bassa": "low",
    "medium": "medium", "medio": "medium", "media": "medium",
    "high": "high", "alto": "high", "alta": "high",
    "original": "original", "originale": "original",
}
LEVELS = ("low", "medium", "high", "original")


def norm_level(word, default=None):
    return LEVEL_ALIASES.get(str(word).strip().lower(), default)


def make_t(lang):
    lang = lang if lang in LANGS else "en"

    def t(key, **kw):
        entry = MSG[key]
        s = entry.get(lang) or entry["en"]
        return s.format(**kw) if kw else s

    t.lang = lang
    return t
