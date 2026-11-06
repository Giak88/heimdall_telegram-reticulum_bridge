# Changelog

## alpha0.1

- First version: a Telegram group or channel bridged to Reticulum/LXMF through a bot.
- Telegram → LXMF: text, photos (WebP, Sideband presets), voice notes (Codec2/Opus), videos and files (fetched on demand with `/download N`), locations, contacts, polls, stickers as text.
- LXMF → Telegram: text, images, voice notes and files posted with the sender's announced name.
- Fixed recipients, optional `/join` subscriptions, echo between LXMF users, `senders = anyone|targets`, block list, per-sender rate limit, fixed names.
- Group → supergroup migration followed; channel posts supported.
- English and Italian; guided `setup.sh` with chat discovery and a maintenance menu; `start|stop|restart|status|logs`.
- Tests: core in both languages, config, catalogue, end-to-end with a fake Bot API, installer against stubs.
