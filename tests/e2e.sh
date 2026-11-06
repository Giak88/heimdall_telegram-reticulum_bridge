#!/usr/bin/env bash
# End-to-end test with no network: a private rnsd, the real bridge, a fake Telegram Bot API
# and a fake LXMF client. Usage: tests/e2e.sh [python] [en|it]
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${1:-python3}"; LANG_="${2:-en}"
W="$(mktemp -d)"; PIDS=()
cleanup() { for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done; rm -rf "$W"; }
trap cleanup EXIT
mkdir -p "$W/rns" "$W/data" "$W/tg"
export NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
PORT=$((37000 + RANDOM % 2000)); TGPORT=$((PORT + 2))
cat > "$W/rns/config" <<CFG
[reticulum]
  enable_transport = No
  share_instance = Yes
  shared_instance_port = $PORT
  instance_control_port = $((PORT + 1))
[logging]
  loglevel = 3
[interfaces]
CFG
"$PY" - "$W" <<'PYEOF'
import sys, RNS
w = sys.argv[1]
i = RNS.Identity(); i.to_file(f"{w}/client.id")
open(f"{w}/client.hash", "w").write(RNS.Destination.hash(i, "lxmf", "delivery").hex())
PYEOF
"$PY" tests/make_media.py "$W/media" >/dev/null
mkdir -p "$W/tg/files" && cp "$W/media/foto.jpg" "$W/tg/files/F_PHOTO"
cat > "$W/config.ini" <<CFG
[bridge]
language = $LANG_
dir = $W/data
rns_config = $W/rns
announce_min = 1
[telegram]
token = 123:TEST
chat_id = -100555
api_base = http://127.0.0.1:$TGPORT
[lxmf]
targets = $(cat "$W/client.hash")
CFG

"$PY" tests/fake_tg.py "$TGPORT" "$W/tg" > "$W/tg.log" 2>&1 & PIDS+=($!)
"$PY" -m RNS.Utilities.rnsd --config "$W/rns" > "$W/rnsd.log" 2>&1 & PIDS+=($!)
sleep 3
"$PY" bridge/heimdall.py "$W/config.ini" > "$W/bridge.log" 2>&1 & PIDS+=($!)
for _ in $(seq 1 30); do [ -s "$W/data/address.txt" ] && break; sleep 1; done
[ -s "$W/data/address.txt" ] || { echo "FAILED: no address.txt"; cat "$W/bridge.log"; exit 1; }
BRIDGE="$(cat "$W/data/address.txt")"; echo "bridge address: $BRIDGE"

# messages "written in the Telegram group" while the client is running
( sleep 14
  echo '[{"message_id":1,"chat":{"id":-100555,"type":"supergroup","title":"Radio"},"from":{"first_name":"Anna"},"text":"hello from Telegram"},
         {"message_id":2,"chat":{"id":-100555,"type":"supergroup","title":"Radio"},"from":{"first_name":"Anna"},"photo":[{"file_id":"F_PHOTO","file_size":75000}],"caption":"look"},
         {"message_id":3,"chat":{"id":-999,"type":"group","title":"Other"},"from":{"first_name":"X"},"text":"not bridged"}]' > "$W/tg/inbox/1.json" ) &
WAIT=16 "$PY" tests/e2e_client.py "$W/rns" "$W" "$BRIDGE" > "$W/client.log" 2>&1
sleep 2
echo "--- client received:"; grep RECEIVED "$W/client.log"
echo "--- posted on Telegram:"; cut -c1-200 "$W/tg/sent.jsonl" 2>/dev/null

fail=0
need() { grep -q -- "$2" "$1" || { echo "FAILED: $3"; fail=1; }; }
need "$W/client.log" "RECEIVED: 'Anna: hello from Telegram'" "Telegram text did not reach the LXMF client"
need "$W/client.log" "RECEIVED: 'Anna: look' \[6\]" "Telegram photo did not reach the LXMF client"
need "$W/client.log" "Heimdall alpha" "/status got no answer"
need "$W/tg/sent.jsonl" '"sendMessage".*<b>Test client</b>: hello from the LoRa' "LXMF text not posted with the client's name"
need "$W/tg/sent.jsonl" '"sendPhoto".*<b>Test client</b>: a photo' "LXMF photo not posted"
! grep -q "not bridged" "$W/client.log" || { echo "FAILED: other chat bridged"; fail=1; }
[ "$fail" = 0 ] && echo "E2E PASSED ($LANG_)" || { echo "--- bridge log:"; tail -30 "$W/bridge.log"; exit 1; }
