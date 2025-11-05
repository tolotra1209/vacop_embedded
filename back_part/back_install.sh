#!/usr/bin/env bash
# back_part/back_install.sh
# Installe les paquets OS, crée le venv et installe les requirements.

set -euo pipefail

echo "[INSTALL] Starting…"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="${VENV_DIR:-.venv}"
REQ_FILE="${REQ_FILE:-$PROJECT_ROOT/back_part/requirements.txt}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

if need_cmd apt-get; then
  echo "[INSTALL] Installing OS packages (RPi.GPIO, CAN utils, venv tool)…"
  sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    python3-rpi.gpio can-utils python3-venv python3-dev build-essential
  echo "[INSTALL] OS packages installed."
else
  echo "[INSTALL][WARN] apt-get not found (container?). Skipping OS install."
fi

echo "[INSTALL] Creating venv: $PROJECT_ROOT/$VENV_DIR (with --system-site-packages)…"
python3 -m venv "$PROJECT_ROOT/$VENV_DIR" --system-site-packages

# shellcheck disable=SC1090
source "$PROJECT_ROOT/$VENV_DIR/bin/activate"

python -m pip install --upgrade pip

if [ -f "$REQ_FILE" ]; then
  echo "[INSTALL] pip install -r $REQ_FILE"
  python -m pip install -r "$REQ_FILE"
else
  echo "[INSTALL][WARN] No requirements.txt at $REQ_FILE"
fi

# Sanity checks
python - <<'PY'
try:
    import RPi.GPIO as G
    print(f"[CHECK] RPi.GPIO OK ->", getattr(G, "__file__", "?"), "| has setmode:", hasattr(G, "setmode"))
except Exception as e:
    print("[CHECK][WARN] RPi.GPIO import issue:", e)
try:
    import can
    print("[CHECK] python-can OK")
except Exception as e:
    print("[CHECK][WARN] python-can import issue:", e)
PY

echo "[INSTALL] ✅ Done. You can now run ./back_part/back_run.sh"

