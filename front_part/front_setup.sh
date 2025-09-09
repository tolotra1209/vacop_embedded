#!/usr/bin/env bash
# front_part/front_setup.sh
# Prépare venv, active CAN, lance front_part.DeviceManager (-v)
# DEBUG=1 ./front_part/front_setup.sh  -> mode verbeux (trace)

# --- DEBUG / Traps ---
if [ "${DEBUG:-0}" = "1" ]; then
  set -x
fi
set -u  # pas de 'exit' auto: on gère nous-mêmes had_error
trap 'code=$?; echo "[TRAP] Script terminé avec code $code";' EXIT
trap 'echo "[TRAP] Erreur à la ligne $LINENO";' ERR

echo "[BOOT] front_setup.sh starting…"  # early echo pour valider le démarrage

# --- Config (overrides via env) ---
CAN_IFACE="${CAN_IFACE:-can0}"
CAN_BITRATE="${CAN_BITRATE:-1000000}"
VENV_DIR="${VENV_DIR:-.venv}"
REQ_FILE="${REQ_FILE:-}"      # si vide -> auto-détection
PY_PKG="front_part"
PY_MOD="DeviceManager"

# --- Localisation ---
# IMPORTANT: nécessite bash, pas sh. Sur bash, BASH_SOURCE est défini.
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

find_requirements() {
  if [ -n "${REQ_FILE:-}" ] && [ -f "$PROJECT_ROOT/$REQ_FILE" ]; then
    echo "$PROJECT_ROOT/$REQ_FILE"; return
  fi
  if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo "$PROJECT_ROOT/requirements.txt"; return
  fi
  if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    echo "$SCRIPT_DIR/requirements.txt"; return
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
    info "Création venv: $PROJECT_ROOT/$VENV_DIR"
    if ! python3 -m venv "$PROJECT_ROOT/$VENV_DIR"; then
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

  info "MàJ pip & install deps…"
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
    warn "Aucun requirements.txt trouvé (racine/front_part)."
  fi

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
  if sudo ip link set "$CAN_IFACE" up type can bitrate "$CAN_BITRATE"; then
    ok "CAN up."
  else
    err "Échec activation CAN."
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

  err "Introuvable: $PY_PKG/$PY_MOD.py (racine) ou $PY_MOD.py (front_part)."
  had_error=1
  return 1
}

info "Démarrage… (IFACE=${CAN_IFACE}, BITRATE=${CAN_BITRATE}, VENV=${VENV_DIR})"
setup_python_env
enable_can
run_app

if [ "$had_error" -ne 0 ]; then
  warn "Terminé avec quelques problèmes."
else
  ok "Tous les étapes OK."
fi
# ne pas 'exit 1' -> on ne ferme pas le terminal

