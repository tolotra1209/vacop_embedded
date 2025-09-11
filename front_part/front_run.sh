#!/usr/bin/env bash
# front_part/front_run.sh
# Active le CAN et lance front_part.DeviceManager (-v)

set -euo pipefail
trap 'code=$?; echo "[TRAP] Script terminé avec code $code";' EXIT

# --- Config ---
CAN_IFACE="${CAN_IFACE:-can0}"
CAN_BITRATE="${CAN_BITRATE:-1000000}"
CAN_RESTART_MS="${CAN_RESTART_MS:-100}"
CAN_TXQLEN="${CAN_TXQLEN:-1024}"

VENV_DIR="${VENV_DIR:-.venv}"
PY_PKG="front_part"
PY_MOD="DeviceManager"

# --- Localisation ---
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

info()  { printf "\033[1;34m[INFO]\033[0m %s\n" "$*"; }
ok()    { printf "\033[1;32m[DONE]\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m[WARN]\033[0m %s\n" "$*"; }
err()   { printf "\033[1;31m[ERR ]\033[0m %s\n" "$*"; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { err "Commande requise manquante: $1"; return 1; }
}

echo "[BOOT] front_run.sh starting…"

# --- venv ---
need_cmd python3
# shellcheck disable=SC1090
source "$PROJECT_ROOT/$VENV_DIR/bin/activate" || { err "Échec activation venv ($VENV_DIR)."; exit 1; }

# --- CAN up ---
need_cmd ip
info "CAN '$CAN_IFACE' @ ${CAN_BITRATE} bps…"
if ! ip link show "$CAN_IFACE" >/dev/null 2>&1; then
  err "Interface '$CAN_IFACE' introuvable. Ex: sudo modprobe can can_raw mcp251x (ou votre driver)"
  exit 1
fi
sudo ip link set "$CAN_IFACE" down >/dev/null 2>&1 || true
sudo ip link set "$CAN_IFACE" type can bitrate "$CAN_BITRATE" restart-ms "$CAN_RESTART_MS"
sudo ip link set "$CAN_IFACE" txqueuelen "$CAN_TXQLEN" || true
sudo ip link set "$CAN_IFACE" up
ok "CAN up."
ip -details -statistics link show "$CAN_IFACE" | sed 's/^/   /'

# --- Lancement Python ---
info "Préparation import Python…"
if [ -d "$PROJECT_ROOT/$PY_PKG" ]; then
  [ -f "$PROJECT_ROOT/$PY_PKG/__init__.py" ] || touch "$PROJECT_ROOT/$PY_PKG/__init__.py"
fi
export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

if [ -f "$PROJECT_ROOT/$PY_PKG/$PY_MOD.py" ]; then
  info "Run module: python3 -m ${PY_PKG}.${PY_MOD} -v (cwd=$PROJECT_ROOT)"
  cd "$PROJECT_ROOT"
  exec python3 -m "${PY_PKG}.${PY_MOD}" -v
else
  err "Introuvable: $PY_PKG/$PY_MOD.py"
  exit 1
fi

