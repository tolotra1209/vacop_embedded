#!/usr/bin/env bash
# back_part/back_run.sh
# Active le CAN et lance l'OBU avec le venv prêt.
# Usage: ./back_part/back_run.sh

set -euo pipefail

CAN_IFACE="${CAN_IFACE:-can0}"
CAN_BITRATE="${CAN_BITRATE:-1000000}"
CAN_RESTART_MS="${CAN_RESTART_MS:-100}"   # aide à sortir du BUS-OFF
CAN_TXQLEN="${CAN_TXQLEN:-1024}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="${VENV_DIR:-.venv}"
PY_PKG="back_part"
PY_MOD="OBU"

info()  { printf "\033[1;34m[INFO]\033[0m %s\n" "$*"; }
ok()    { printf "\033[1;32m[DONE]\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m[WARN]\033[0m %s\n" "$*"; }
err()   { printf "\033[1;31m[ERR ]\033[0m %s\n" "$*"; }

info "Starting (IFACE=${CAN_IFACE}, BITRATE=${CAN_BITRATE}, VENV=${VENV_DIR})"

# CAN up (idempotent)
if command -v ip >/dev/null 2>&1; then
  if ip link show "$CAN_IFACE" >/dev/null 2>&1; then
    sudo ip link set "$CAN_IFACE" down >/dev/null 2>&1 || true
    sudo ip link set "$CAN_IFACE" type can bitrate "$CAN_BITRATE" restart-ms "$CAN_RESTART_MS"
    sudo ip link set "$CAN_IFACE" txqueuelen "$CAN_TXQLEN" || true
    sudo ip link set "$CAN_IFACE" up
    ok "CAN up."
    ip -details -statistics link show "$CAN_IFACE" | sed 's/^/   /'
  else
    warn "Interface '$CAN_IFACE' introuvable. Vérifiez l'overlay MCP2515 et le câblage."
  fi
else
  warn "'ip' command not found; skipping CAN bring-up."
fi

# venv
if [ ! -d "$PROJECT_ROOT/$VENV_DIR" ]; then
  err "Venv not found at $PROJECT_ROOT/$VENV_DIR. Run back_install.sh first."
  exit 1
fi

# shellcheck disable=SC1090
source "$PROJECT_ROOT/$VENV_DIR/bin/activate"

# Python import path
[ -d "$PROJECT_ROOT/$PY_PKG" ] && [ -f "$PROJECT_ROOT/$PY_PKG/__init__.py" ] || touch "$PROJECT_ROOT/$PY_PKG/__init__.py"
export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

# Run
info "Run module: python3 -m ${PY_PKG}.${PY_MOD} -v (cwd=$PROJECT_ROOT)"
cd "$PROJECT_ROOT"
exec python3 -m "${PY_PKG}.${PY_MOD}" -v

