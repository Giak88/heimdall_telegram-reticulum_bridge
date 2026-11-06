#!/usr/bin/env bash
# Runs every offline test. Usage: tests/run_tests.sh [python]   (default: python3)
# Needs ffmpeg (libopus + libcodec2), Pillow, and for test_config also rns + lxmf.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${1:-python3}"
M="$(mktemp -d)"; trap 'rm -rf "$M"' EXIT
"$PY" tests/make_media.py "$M"
"$PY" tests/test_i18n.py
"$PY" tests/test_config.py
for L in en it; do "$PY" tests/test_core.py "$M" "$L" | tail -1; done
echo "ALL TESTS PASSED"
