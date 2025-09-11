#!/usr/bin/env bash
# front_part/front_install.sh
# Installe les dépendances OS, prépare le venv et installe les deps Python.

set -euo pipefail
trap 'code=$?; echo "[TRAP] Script terminé avec code $code";' EXIT

# --- Config (overrides via env) ---
VENV_DIR="${VENV_DIR:-.venv}"
REQ_FILE="${REQ_FILE:-}"   # si vide -> auto-détection

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

find_requirements() {
  if [ -n "${REQ_FILE:-}" ] && [ -f "$PROJECT_ROOT/$REQ_FILE" ]; then
    echo "$PROJECT_ROOT/$REQ_FILE"; return
  fi
  if [ -f "$PROJECT_ROOT/front_part/requirements.txt" ]; then
    echo "$PROJECT_ROOT/front_part/requirements.txt"; return
  fi
  if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo "$PROJECT_ROOT/requirements.txt"; return
  fi
  echo ""
}

echo "[BOOT] front_install.sh starting…"

# --- Paquets système (RPi.GPIO via apt recommandé) ---
if command -v apt-get >/dev/null 2>&1; then
  info "Installation des paquets système (RPi.GPIO, can-utils)…"
  sudo apt-get update -y || warn "apt-get update KO (on continue)"
  sudo apt-get install -y --no-install-recommends \
    python3-venv python3-dev build-essential \
    python3-rpi.gpio can-utils \
    || err "apt-get install a rencontré un problème."
  ok "Paquets système installés (ou déjà présents)."
else
  warn "apt-get introuvable (container/OS non debian). Skip install OS deps."
fi

# --- venv ---
need_cmd python3
if ! python3 -m venv -h >/dev/null 2>&1; then
  err "Module venv absent (sudo apt-get install -y python3-venv)."
  exit 1
fi
if [ ! -d "$PROJECT_ROOT/$VENV_DIR" ]; then
  info "Création venv: $PROJECT_ROOT/$VENV_DIR (avec --system-site-packages)"
  python3 -m venv "$PROJECT_ROOT/$VENV_DIR" --system-site-packages
fi

# shellcheck disable=SC1090
source "$PROJECT_ROOT/$VENV_DIR/bin/activate"

info "MàJ pip…"
python -m pip install --upgrade pip >/dev/null 2>&1 || warn "pip upgrade KO (on continue)."

req_path="$(find_requirements)"
if [ -n "$req_path" ]; then
  info "Installation deps Python: $req_path"
  python -m pip install -r "$req_path"
  ok "Dépendances Python installées."
else
  warn "Aucun requirements.txt trouvé (front_part/ ou racine)."
fi

# --- Sanity-check imports clés ---
python - <<'PY'
try:
    import RPi.GPIO as G
    print(f"[CHECK] RPi.GPIO OK ->", getattr(G, "__file__", "?"))
except Exception as e:
    print("[CHECK][WARN] RPi.GPIO indisponible:", e)

for mod in ("can", "Adafruit_MCP3008", "Adafruit_GPIO"):
    try:
        __import__(mod)
        print(f"[CHECK] {mod} import OK")
    except Exception as e:
        print(f"[CHECK][WARN] {mod} import KO:", e)
PY

ok "Installation front_part terminée."

