# Heimdall

**English** · [Italiano](README.it.md)

A bridge between a **Telegram group or channel** and **Reticulum / LXMF**. Heimdall has its own LXMF address: whatever anyone writes to that address from Sideband or MeshChatX is posted in the Telegram chat with the sender's name, and whatever is written in the Telegram chat reaches the LXMF addresses you choose — over LoRa, TCP, or whatever your Reticulum network is made of. Photos, voice notes and files go both ways, squeezed to fit a radio link.

> **Status: alpha (`alpha0.1`).** Tested end to end against a real `rnsd` and a simulated Telegram Bot API. Sister project of [Bifrost](https://github.com/Giak88/bifrost_whatsapp-reticulum_bridge) (WhatsApp ⇄ Reticulum).

```
Telegram group/channel ── Bot API ── Heimdall (Python) ── rnsd (shared instance) ── RNode / TCP / ...
```

Heimdall **never opens your radio**: it is a client of the `rnsd` shared instance, like Sideband or MeshChatX, so they can all run on the same node. Pure Python: no Node.js.

## Features

- **Telegram → LXMF**: messages of the bridged chat go to every configured LXMF recipient as `Name: text`
- **LXMF → Telegram**: anyone (or only the recipients, your choice) writes to the bridge's address and it is posted as **Name**: text, with the name the sender announces on Reticulum
- Photos become WebP (Sideband's presets), voice notes become Codec2 or Opus; quality configurable
- **Confirmation for big media**: above a threshold (32 KB) recipients get a notice with size and airtime, and fetch it with `/download N`. Big videos/files are only downloaded from Telegram when someone asks
- Optional `/join` / `/leave` so LXMF users can subscribe themselves; optional echo between LXMF users
- Per-sender rate limit, block list, fixed names for addresses
- Group → supergroup migration followed automatically; channels supported (bot as admin)
- English and Italian: bot replies, logs, commands (`/download` = `/scarica`, ...), installer
- Guided installer `setup.sh` with a maintenance menu

## Requirements

- A Linux box with **systemd** (developed on Debian 13)
- **Reticulum** (`rnsd`) installed and running with your radio/network configured
- Python 3 with `venv`, **ffmpeg built with libcodec2 and libopus** (the stock Debian/Ubuntu `ffmpeg` has both)
- A **Telegram bot dedicated to Heimdall** (create it with [@BotFather](https://t.me/BotFather), `/newbot`)
- For a **group**: turn the bot's privacy mode off (@BotFather → `/setprivacy` → Disable), otherwise it only sees commands. Do it *before* adding the bot to the group (or remove and re-add it)
- For a **channel**: add the bot as an administrator allowed to post

## Quick start

```bash
git clone https://github.com/Giak88/heimdall_telegram-reticulum_bridge.git
cd heimdall_telegram-reticulum_bridge
./setup.sh                 # asks for the language, then walks you through everything
```

The installer checks the dependencies (and offers to install them), checks `rnsd`, creates the Python environment in `~/.heimdall/venv`, runs a self-test, then asks for:

1. the **bot token** (checked with Telegram; warns if privacy mode is on)
2. the **chat**: add the bot to the group and write any message there — the installer sees it and lists it, you pick it (or type its id)
3. the **LXMF recipients**: the addresses that will receive the Telegram messages (32 hex characters each, comma-separated)

then installs and starts the `heimdall` service and prints **the bridge's LXMF address**. Write to it from Sideband: it shows up in the Telegram chat.

Unattended: `./setup.sh --lang en --yes --token <token> --chat <id> --targets <hash>[,<hash>...]`.

## Starting, stopping, restarting

```bash
./setup.sh start        # (re)start
./setup.sh stop
./setup.sh restart      # after editing config.ini
./setup.sh status       # service state, bridge address, chat, recipients
./setup.sh logs         # follow the log (Ctrl+C to leave)
./setup.sh              # menu: the above, plus token, chat, recipients, who can write,
                        # media quality, language, update, uninstall
```

Directly with systemd: `sudo systemctl restart|stop|start heimdall`, `sudo systemctl disable --now heimdall` to keep it off at boot.

## Using it from Reticulum

Write to the bridge's address like to any LXMF contact. Plain text, photos, voice notes and files are posted in the Telegram chat. Commands:

| Command | What it does |
|---|---|
| `/download N` | fetch media number N that was held back because of its size (recipients only) |
| `/status` | version, Telegram state, chat, number of recipients, held media |
| `/join`, `/leave` | receive the Telegram chat here / stop (only if `subscriptions = yes`) |
| `/help` | the list |

Italian aliases: `/scarica`, `/stato`, `/entra`, `/esci`, `/aiuto`.

Senders are shown on Telegram with the display name they announce (Sideband's "display name"), or `<first 8 hex>` if the bridge has not heard their announce yet. Fixed names can be set in `[names]`.

## Media

| Telegram → LXMF | |
|---|---|
| photo | WebP at `quality_img`: `low` 320 px q22 · `medium` 640 px q66 · `high` 1280 px q75 · `original` |
| voice note / audio | `quality_audio`: `low` Codec2 2400 · `medium` Opus 12 kbps · `high` Opus 24 kbps · `original` |
| video, GIF, document | unchanged, fetched from Telegram only when someone sends `/download N` |
| location, contact, poll, sticker | as text (locations with an OpenStreetMap link) |

If a converted photo/voice note exceeds `max_file_mb` it steps down a level by itself. Anything above `confirm_threshold_kb` (32) after conversion is held for `/download N`; above `max_file_mb` (0.9: stock LXMF routers refuse more than 1000 KB) it cannot be delivered. Telegram bots can download at most 20 MB.

| LXMF → Telegram | |
|---|---|
| image | photo (JPEG) |
| audio (Codec2 or Opus) | voice note |
| file | video if it is a video, otherwise document (Telegram bot limit: 50 MB) |

Heimdall accepts LXMF messages up to `max_receive_mb` (10). Over LoRa, sending megabytes takes a long time: compress in Sideband when sending.

## Configuration

`~/.heimdall/config.ini` (commented template: [`config.example.ini`](config.example.ini)). After editing: `./setup.sh restart`.

| Key | Default | Meaning |
|---|---|---|
| `[bridge] language` | `en` | `en` or `it` |
| `max_receive_mb` | 10 | biggest LXMF message accepted |
| `[telegram] token`, `chat_id` | – | the bot and the bridged chat |
| `[lxmf] targets` | – | addresses that receive the Telegram chat |
| `senders` | `anyone` | who may post: `anyone` or `targets` |
| `subscriptions` | `no` | allow `/join` |
| `echo` | `no` | repeat an LXMF user's post to the other LXMF recipients |
| `blocked` | – | addresses always ignored |
| `[limits] confirm_threshold_kb` | 32 | hold media above this size |
| `max_file_mb` | 0.9 | never deliver above this |
| `quality_img`, `quality_audio` | `low` | see Media |
| `rate_per_min` | 10 | per-sender limit (0 = none) |
| `[names] <hash> = Name` | – | fixed display names |

## Logs and troubleshooting

`./setup.sh logs` (or `sudo journalctl -u heimdall -f`). The bridge address is also in `~/.heimdall/address.txt`.

| Symptom | Likely cause |
|---|---|
| Nothing arrives from the group | privacy mode still on: @BotFather → `/setprivacy` → Disable, then remove and re-add the bot |
| `another program is reading this bot's updates` | the token is used elsewhere (webhook or another copy): use a dedicated bot |
| Posting fails with `Forbidden` / `not enough rights` | in a channel the bot must be an admin allowed to post |
| A message is "lost" in the log | the recipient was unreachable: 4 attempts 30 s apart, then the propagation node if configured |
| Sender shown as `<abcd1234>` | the bridge has not received their announce yet; or set a name in `[names]` |
| Journal full of `Pathing` lines | `loglevel` in `~/.reticulum/config` too high (use 4) |

## Known limits

- One bridged chat per installation (an LXMF router supports one delivery identity). Run a second copy with another `HEIMDALL_HOME` for a second chat.
- Replies, edits, deletions and reactions on Telegram are not carried over; topics (forum threads) are not distinguished.
- Media held for `/download` expire after `pending_ttl_h` (24 h).
- The propagation-node fallback is implemented but not field-tested.

## Security notes

- The bot token is in `~/.heimdall/config.ini` (mode 600): anyone with it controls the bot.
- With `senders = anyone`, anybody on the Reticulum network can post in your Telegram chat. Use `targets`, `blocked` and `rate_per_min` accordingly.
- Telegram bot chats are not end-to-end encrypted, and the bridge host sees everything in clear.

## Development

```bash
tests/run_tests.sh              # catalogue, config, core (EN and IT); needs rns + lxmf + Pillow + ffmpeg
tests/e2e.sh python3 en         # private rnsd + real bridge + fake Telegram Bot API + fake LXMF client
tests/test_setup.sh             # setup.sh against stubbed sudo/systemctl and the fake Bot API
```

## Credits

Idea and field testing by [Giak88](https://github.com/Giak88). Designed and written with Claude (Anthropic).
Built on [Reticulum](https://reticulum.network) and [LXMF](https://github.com/markqvist/LXMF) by Mark Qvist and the [Telegram Bot API](https://core.telegram.org/bots/api), following [Sideband](https://github.com/markqvist/Sideband)'s media conventions. Not affiliated with Telegram.

## License

MIT, see [LICENSE](LICENSE).
