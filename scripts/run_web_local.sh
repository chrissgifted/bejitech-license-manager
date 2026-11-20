#!/usr/bin/env bash
# Run the Bejitech web version on this computer (macOS or Linux), before it goes online.
#
#   ./scripts/run_web_local.sh            open from this computer and from phones/tablets on the same Wi-Fi
#   LOCAL_ONLY=1 ./scripts/run_web_local.sh   open from this computer only
#
# Data lives in ~/BejitechWeb (separate from the desktop app's data). The first run creates
# ~/BejitechWeb/web.env with the secret keys: keep a copy of that file somewhere safe.
set -euo pipefail
cd "$(dirname "$0")/.."

DATA="${BEJITECH_DATA_DIR:-$HOME/BejitechWeb}"
PORT="${PORT:-8000}"
mkdir -p "$DATA"
chmod 700 "$DATA"

PY=""
for c in python3.13 python3.12 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.12 or newer is needed. Install it from https://www.python.org/downloads/ and run this again."
  exit 1
fi

if [ ! -d .venv-web ]; then
  echo "First run: setting up (takes a minute or two)…"
  "$PY" -m venv .venv-web
fi
# shellcheck disable=SC1091
source .venv-web/bin/activate
pip install -q --upgrade pip >/dev/null
pip install -q -r requirements-web.txt

export PYTHONPATH=src
if [ ! -f "$DATA/web.env" ]; then
  python -m bejitech.web genkey > "$DATA/web.env"
  chmod 600 "$DATA/web.env"
  echo "Created $DATA/web.env (your secret keys). Keep a copy somewhere safe."
fi
set -a
# shellcheck disable=SC1091
source "$DATA/web.env"
set +a
export BEJITECH_DATA_DIR="$DATA" BEJITECH_COOKIE_SECURE=0 PORT
export TZ="${TZ:-Africa/Dar_es_Salaam}"

if [ "${LOCAL_ONLY:-0}" = "1" ]; then
  export HOST=127.0.0.1
else
  export HOST=0.0.0.0
fi

IP=""
if command -v ipconfig >/dev/null 2>&1; then
  IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
elif command -v hostname >/dev/null 2>&1; then
  IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
fi

echo
echo "Bejitech License Manager (web) is starting."
echo "  On this computer:   http://localhost:$PORT"
if [ "$HOST" = "0.0.0.0" ] && [ -n "$IP" ]; then
  echo "  Phone / tablet:     http://$IP:$PORT   (same Wi-Fi only)"
fi
echo "  Setup code (only needed the very first time): $BEJITECH_SETUP_TOKEN"
echo "  Data folder:        $DATA"
echo "Leave this window open while you use it. Press Ctrl+C to stop."
echo
exec python -m bejitech.web serve
