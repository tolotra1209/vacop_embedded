#!/usr/bin/env bash
# back_part/back_setup.sh
# Prépare venv, installe RPi.GPIO (apt), active CAN, lance back_part.OBU (-v)
# DEBUG=1 ./back_part/back_setup.sh  -> mode verbeux (trace)

# --- DEBUG / Traps ---
if [ "${DEBUG:-0}" = "1" ]; then
  set -x
fi
set -u
trap 'code=$?; echo "[TRAP] Script terminé avec code $code";' EXIT
trap 'echo "[TRAP] Erreur à la ligne $LINENO";' ERR

echo "[BOOT] back_setup.sh starting…"

# --- Config (overrides via env) ---
CAN_IFACE="${CAN_IFACE:-can0}"
CAN_BITRATE="${CAN_BITRATE:-1000000}"
CAN_RESTART_MS="${CAN_RESTART_MS:-100}"
CAN_TXQLEN="${CAN_TXQLEN:-1024}"

VENV_DIR="${VENV_DIR:-.venv}"
REQ_FILE="${REQ_FILE:-}"      # si vide -> auto-détection
PY_PKG="back_part"
PY_MOD="OBU"

# --- Localisation ---
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- UI helpers ---
info()  { printf "\033[1;34m[INFO]\033[0m %s\n" "$*"; }
ok()    { printf "\033[1;32m[DONE]\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m[WARN]\033[0m %s\n" "$*"; }
err()   { printf "\033[1;31m[ERR ]\033[0m %s\n" "$*"; }

had_error=0

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "Commande requise manquante: $1"
    had_error=1
    return 1
  fi
  return 0
}

install_os_packages() {
  info "Installation des paquets système requis (RPi.GPIO, CAN utils)…"
  need_cmd apt-get || { warn "apt-get introuvable (container ?). On continue sans OS deps."; return 0; }

  sudo apt-get update -y || warn "apt-get update KO (on continue)"
  # RPi.GPIO en paquets système (plus fiable que pip), + can-utils pratique
  sudo apt-get install -y --no-install-recommends \
    python3-rpi.gpio can-utils python3-dev build-essential \
    || err "apt-get install a rencontré un problème (RPi.GPIO/can-utils)."

  ok "Paquets système installés (ou déjà présents)."
}

find_requirements() {
  if [ -n "${REQ_FILE:-}" ] && [ -f "$PROJECT_ROOT/$REQ_FILE" ]; then
    echo "$PROJECT_ROOT/$REQ_FILE"; return
  fi
  if [ -f "$PROJECT_ROOT/$PY_PKG/requirements.txt" ]; then
    echo "$PROJECT_ROOT/$PY_PKG/requirements.txt"; return
  fi
  if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo "$PROJECT_ROOT/requirements.txt"; return
  fi
  echo ""
}

setup_python_env() {
  info "Vérification Python…"
  need_cmd python3 || return 1
  if ! python3 -m venv -h >/dev/null 2>&1; then
    err "Module venv absent (sudo apt-get install -y python3-venv)."
    had_error=1
    return 1
  fi

  if [ ! -d "$PROJECT_ROOT/$VENV_DIR" ]; then
    info "Création venv: $PROJECT_ROOT/$VENV_DIR (avec --system-site-packages)"
    if ! python3 -m venv "$PROJECT_ROOT/$VENV_DIR" --system-site-packages; then
      err "Échec création venv."
      had_error=1
      return 1
    fi
  fi

  # shellcheck disable=SC1090
  if ! source "$PROJECT_ROOT/$VENV_DIR/bin/activate"; then
    err "Échec activation venv."
    had_error=1
    return 1
  fi

  info "MàJ pip & install deps Python (pip)…"
  python -m pip install --upgrade pip >/dev/null 2>&1 || warn "pip upgrade KO (on continue)."

  local req_path
  req_path="$(find_requirements)"
  if [ -n "$req_path" ]; then
    info "requirements: $req_path"
    if ! python -m pip install -r "$req_path"; then
      err "pip install -r KO"
      had_error=1
    else
      ok "Dépendances installées."
    fi
  else
    warn "Aucun requirements.txt trouvé (racine/back_part)."
  fi

  # Sanity-check RPi.GPIO
  python - <<'PY'
import sys
try:
    import RPi.GPIO as G
    print(f"[CHECK] RPi.GPIO OK ->", getattr(G, "__file__", "?"), "| has setmode:", hasattr(G,"setmode"))
    assert hasattr(G, "setmode"), "RPi.GPIO importé mais sans setmode() !"
except Exception as e:
    print("[CHECK][WARN] Problème RPi.GPIO:", e)
PY

  ok "Environnement Python prêt."
}

enable_can() {
  info "CAN '$CAN_IFACE' @ ${CAN_BITRATE} bps…"
  need_cmd ip || return 1

  if ! ip link show "$CAN_IFACE" >/dev/null 2>&1; then
    warn "Interface '$CAN_IFACE' introuvable. Drivers/naming ?"
    warn "Ex: sudo modprobe can can_raw mcp251x (ou votre driver)"
    had_error=1
    return 1
  fi

  sudo ip link set "$CAN_IFACE" down >/dev/null 2>&1 || true
  # on grossit la queue TX et on active restart-ms pour sortir de BUS-OFF
  if sudo ip link set "$CAN_IFACE" type can bitrate "$CAN_BITRATE" restart-ms "$CAN_RESTART_MS"; then
    sudo ip link set "$CAN_IFACE" txqueuelen "$CAN_TXQLEN" || true
    if sudo ip link set "$CAN_IFACE" up; then
      ok "CAN up."
      ip -details -statistics link show "$CAN_IFACE" | sed 's/^/   /'
    else
      err "Échec 'ip link set up' sur $CAN_IFACE."
      had_error=1
    fi
  else
    err "Échec configuration CAN (bitrate/restart-ms)."
    had_error=1
  fi
}

run_app() {
  info "Préparation import Python…"
  if [ -d "$PROJECT_ROOT/$PY_PKG" ]; then
    [ -f "$PROJECT_ROOT/$PY_PKG/__init__.py" ] || touch "$PROJECT_ROOT/$PY_PKG/__init__.py"
  fi
  export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

  if [ -f "$PROJECT_ROOT/$PY_PKG/$PY_MOD.py" ]; then
    info "Run module: python3 -m ${PY_PKG}.${PY_MOD} -v (cwd=$PROJECT_ROOT)"
    if ( cd "$PROJECT_ROOT" && python3 -m "${PY_PKG}.${PY_MOD}" -v ); then
      ok "Application terminée."
      return 0
    else
      err "Module KO."
      had_error=1
    fi
  fi

  if [ -f "$SCRIPT_DIR/$PY_MOD.py" ]; then
    info "Fallback: python3 $PY_MOD.py -v (cwd=$SCRIPT_DIR)"
    if ( cd "$SCRIPT_DIR" && python3 "$PY_MOD.py" -v ); then
      ok "Application terminée (fallback)."
      return 0
    else
      err "Fallback KO."
      had_error=1
      return 1
    fi
  fi

  err "Introuvable: $PY_PKG/$PY_MOD.py (racine) ou $PY_MOD.py (back_part)."
  had_error=1
  return 1
}

info "Démarrage… (IFACE=${CAN_IFACE}, BITRATE=${CAN_BITRATE}, VENV=${VENV_DIR})"
install_os_packages
setup_python_env
enable_can
run_app

if [ "$had_error" -ne 0 ]; then
  warn "Terminé avec quelques problèmes."
else
  ok "Toutes les étapes OK."
fi
# ne pas 'exit 1' -> on ne ferme pas le terminal

