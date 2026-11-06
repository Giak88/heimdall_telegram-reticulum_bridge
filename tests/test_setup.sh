#!/usr/bin/env bash
# Tests setup.sh with stubbed sudo/systemctl and a fake Telegram Bot API, in a throwaway HOME.
# Usage: tests/test_setup.sh [wheel_dir]   (wheel_dir: rns/lxmf wheels for an offline pip)
set -uo pipefail
cd "$(dirname "$0")/.."
WHEELS="${1:-}"
T="$(mktemp -d)"; PIDS=()
cleanup() { for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done; rm -rf "$T"; }
trap cleanup EXIT
mkdir -p "$T/bin" "$T/home" "$T/units" "$T/tg"
cat > "$T/bin/sudo" <<'STUB'
#!/usr/bin/env bash
exec "$@"
STUB
cat > "$T/bin/systemctl" <<'STUB'
#!/usr/bin/env bash
echo "systemctl $*" >> "$STUB_LOG"
case "$1" in is-active) exit 0 ;; list-unit-files) echo "rnsd.service enabled" ;; esac
exit 0
STUB
chmod +x "$T/bin/"*
TGPORT=$((39000 + RANDOM % 900))
python3 tests/fake_tg.py "$TGPORT" "$T/tg" > /dev/null 2>&1 & PIDS+=($!)
sleep 1
export PATH="$T/bin:$PATH" HOME="$T/home" STUB_LOG="$T/stub.log" HEIMDALL_UNIT_DIR="$T/units" \
       HEIMDALL_HOME="$T/home/.heimdall" HEIMDALL_ALLOW_ROOT=1 HEIMDALL_ADDR_WAIT=1 \
       HEIMDALL_TG_API="http://127.0.0.1:$TGPORT" NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost
[ -n "$WHEELS" ] && export PIP_NO_INDEX=1 PIP_FIND_LINKS="$WHEELS" PIP_NO_DEPS=1 HEIMDALL_VENV_FLAGS=--system-site-packages
: > "$STUB_LOG"
fail=0
chk() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
A=0123456789abcdef0123456789abcdef; B=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
C="$T/home/.heimdall/config.ini"

for L in en it; do
  rm -rf "$T/home/.heimdall" "$T/units"/*; : > "$STUB_LOG"
  echo "== unattended install, language $L"
  ./setup.sh --lang "$L" --yes --token 123:ABC --chat -100777 --targets "<${A^^}>, $B" > "$T/out.$L" 2>&1 \
    || { echo "FAIL exit code ($L)"; tail -15 "$T/out.$L"; fail=1; }
  chk "[$L] token, chat, targets, language written" "grep -q '^token = 123:ABC' $C && grep -q '^chat_id = -100777' $C && grep -q '^targets = $A, $B' $C && grep -q '^language = $L' $C"
  chk "[$L] config readable only by the user" "[ \"\$(stat -c %a $C)\" = 600 ]"
  chk "[$L] bot checked" "grep -q '@test_bot' $T/out.$L"
  chk "[$L] unit rendered" "grep -q 'ExecStart=$T/home/.heimdall/venv/bin/python heimdall.py $C' $T/units/heimdall.service && grep -q 'Requires=rnsd.service' $T/units/heimdall.service && ! grep -q '@[A-Z_]*@' $T/units/heimdall.service"
  chk "[$L] service enabled and started" "grep -q 'systemctl enable heimdall' $STUB_LOG && grep -q 'systemctl restart heimdall' $STUB_LOG"
  chk "[$L] self-test passed" "grep -q '$( [ $L = it ] && echo 'Autotest superato' || echo 'Self-test passed')' $T/out.$L"
done

echo "== bad inputs"
rm -rf "$T/home/.heimdall"
chk "bad token refused" "! ./setup.sh --lang en --yes --skip-tests --token bad --chat -1 --targets $A > $T/o1 2>&1 && grep -q 'refused the token: Unauthorized' $T/o1"
chk "bad target refused" "! ./setup.sh --lang en --yes --skip-tests --token 1:A --chat -1 --targets 'abc' > $T/o2 2>&1 && grep -q 'Invalid address: abc' $T/o2"
rm -rf "$T/home/.heimdall"
chk "--yes without token refused" "! ./setup.sh --lang en --yes --skip-tests > $T/o3 2>&1 && grep -q -- '--yes needs' $T/o3"

echo "== re-run keeps the config, flags override"
./setup.sh --lang en --yes --skip-tests --token 1:A --chat -100777 --targets $A > /dev/null 2>&1
./setup.sh --lang en --yes --skip-tests --targets $B > "$T/o4" 2>&1
chk "only targets changed" "grep -q '^targets = $B' $C && grep -q '^token = 1:A' $C && grep -q '^chat_id = -100777' $C"

echo "== chat discovery helper"
echo '[{"chat":{"id":-100999,"type":"supergroup","title":"Radio club"},"from":{"first_name":"A"},"text":"hi"}]' > "$T/tg/inbox/x.json"
chk "discover lists the group" "$T/home/.heimdall/venv/bin/python bridge/telegram.py discover 1:A 3 | grep -q -- $'-100999\tsupergroup\tRadio club'"

echo "== start / stop / restart / status"
: > "$STUB_LOG"
./setup.sh --lang it stop > "$T/o5" 2>&1; chk "stop" "grep -q 'systemctl stop heimdall' $STUB_LOG && grep -q 'Servizio fermato' $T/o5"
./setup.sh start > "$T/o6" 2>&1;          chk "start" "grep -q 'systemctl restart heimdall' $STUB_LOG"
./setup.sh status > "$T/o7" 2>&1;         chk "status shows chat and recipients" "grep -q -- '-100777' $T/o7 && grep -q '$B' $T/o7"

echo "== uninstall"
./setup.sh --lang en --yes --uninstall > /dev/null 2>&1
chk "unit removed, data kept" "[ ! -e $T/units/heimdall.service ] && [ -f $C ]"
chk "commands refuse when not installed" "! ./setup.sh stop > $T/o8 2>&1"

[ "$fail" = 0 ] && echo "SETUP TESTS PASSED" || { echo "SETUP TESTS FAILED"; exit 1; }
