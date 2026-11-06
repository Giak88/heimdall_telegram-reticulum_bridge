# Changelog

## alpha0.2

- **`/repeat N` (`/ripeti N`)**: the bridge keeps every message it sent you (`history_h`, default 48 h, up to `history_max`, default 100; photos and voice notes included) and sends the last N again on request, oldest first, marked `↻ HH:MM`. Useful after being out of LoRa coverage. The number is required: `/repeat` alone replies with the usage. Each recipient gets only the messages that were sent to them.
- New `[limits]` keys `history_h` and `history_max` (`history_max = 0` turns the history off).

## alpha0.1

- First version: a Telegram group or channel bridged to Reticulum/LXMF through a bot.
- Telegram → LXMF: text, photos (WebP, Sideband presets), voice notes (Codec2/Opus), videos and files (fetched on demand with `/download N`), locations, contacts, polls, stickers as text.
- LXMF → Telegram: text, images, voice notes and files posted with the sender's announced name.
- Fixed recipients, optional `/join` subscriptions, echo between LXMF users, `senders = anyone|targets`, block list, per-sender rate limit, fixed names.
- Group → supergroup migration followed; channel posts supported.
- English and Italian; guided `setup.sh` with chat discovery and a maintenance menu; `start|stop|restart|status|logs`.
- Tests: core in both languages, config, catalogue, end-to-end with a fake Bot API, installer against stubs.
