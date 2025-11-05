#!/usr/bin/env bash
# middle_part/middle_run.sh
# Active le CAN, assure le venv (auto-création si manquant), lance middle_part.DeviceManager

set -euo pipefail
trap 'code=$?; echo "[TRAP] run terminé avec code $code"' EXIT

# --- Config (surchage possible via env) ---
CAN_IFACE="${CAN_IFACE:-can0}"
CAN_BITRATE="${CAN_BITRATE:-1000000}"
CAN_RESTART_MS="${CAN_RESTART_MS:-100}"
CAN_TXQLEN="${CAN_TXQLEN:-1024}"
VENV_DIR="${VENV_DIR:-.venv}"

# --- Localisation ---
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "[INFO] Starting middle_part (IFACE=$CAN_IFACE, BITRATE=$CAN_BITRATE, VENV=$VENV_DIR)"
echo "[INFO] Project root: $PROJECT_ROOT"

# --- CAN up ---
if command -v ip >/dev/null 2>&1; then
  if ip link show "$CAN_IFACE" >/dev/null 2>&1; then
    sudo ip link set "$CAN_IFACE" down >/dev/null 2>&1 || true
    sudo ip link set "$CAN_IFACE" type can bitrate "$CAN_BITRATE" restart-ms "$CAN_RESTART_MS"
    sudo ip link set "$CAN_IFACE" txqueuelen "$CAN_TXQLEN" || true
    sudo ip link set "$CAN_IFACE" up
    echo "[DONE] CAN up."
    ip -details -statistics link show "$CAN_IFACE" | sed 's/^/   /'
  else
    echo "[WARN] Interface '$CAN_IFACE' introuvable. (drivers ? modprobe can, can_raw, mcp251x …)"
  fi
else
  echo "[WARN] 'ip' introuvable, skip CAN setup."
fi

# --- venv auto-soin : crée si manquant puis active ---
if [ ! -d "$PROJECT_ROOT/$VENV_DIR" ]; then
  echo "[WARN] venv manquant ($PROJECT_ROOT/$VENV_DIR). Création…"
  python3 -m venv "$PROJECT_ROOT/$VENV_DIR" --system-site-packages
  # shellcheck disable=SC1090
  source "$PROJECT_ROOT/$VENV_DIR/bin/activate"
  python -m pip install --upgrade pip
  if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    python -m pip install -r "$SCRIPT_DIR/requirements.txt"
  fi
else
  # shellcheck disable=SC1090
  source "$PROJECT_ROOT/$VENV_DIR/bin/activate"
fi

# PYTHONPATH pour que "python -m middle_part.DeviceManager" voie le package
export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

# --- run ---
if [ -f "$PROJECT_ROOT/middle_part/DeviceManager.py" ]; then
  echo "[INFO] Run module: python3 -m middle_part.DeviceManager -v (cwd=$PROJECT_ROOT)"
  ( cd "$PROJECT_ROOT" && python3 -m middle_part.DeviceManager -v )
else
  echo "[ERR ] Introuvable: middle_part/DeviceManager.py"
  exit 1
fi
