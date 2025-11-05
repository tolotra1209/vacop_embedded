#!/usr/bin/env bash
# middle_part/middle_install.sh
# Crée le venv au NIVEAU RACINE du dépôt et installe les deps de middle_part

set -euo pipefail
trap 'code=$?; echo "[TRAP] install terminé avec code $code"' EXIT

# --- Config (surchage possible via env) ---
VENV_DIR="${VENV_DIR:-.venv}"

# --- Localisation ---
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "[INFO] Install middle_part (VENV_DIR=$VENV_DIR)"
echo "[INFO] Project root: $PROJECT_ROOT"

# 1) Vérifs Python / venv
if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERR ] python3 introuvable."
  exit 1
fi
if ! python3 -m venv -h >/dev/null 2>&1; then
  echo "[ERR ] module venv manquant (sudo apt-get install -y python3-venv)."
  exit 1
fi

# 2) Crée le venv dans la racine du repo (commun à tous)
if [ ! -d "$PROJECT_ROOT/$VENV_DIR" ]; then
  echo "[INFO] Création venv: $PROJECT_ROOT/$VENV_DIR (avec --system-site-packages)"
  python3 -m venv "$PROJECT_ROOT/$VENV_DIR" --system-site-packages
fi

# 3) Active le venv
# shellcheck disable=SC1090
source "$PROJECT_ROOT/$VENV_DIR/bin/activate"

# 4) pip & deps
python -m pip install --upgrade pip

REQ_MP="$SCRIPT_DIR/requirements.txt"
REQ_ROOT="$PROJECT_ROOT/requirements.txt"

if [ -f "$REQ_MP" ]; then
  echo "[INFO] pip install -r $REQ_MP"
  python -m pip install -r "$REQ_MP"
else
  echo "[WARN] middle_part/requirements.txt introuvable."
fi

# Optionnel : si vous avez un requirements global au repo
if [ -f "$REQ_ROOT" ]; then
  echo "[INFO] (optionnel) pip install -r $REQ_ROOT"
  python -m pip install -r "$REQ_ROOT" || true
fi

echo "[DONE] middle_part install OK."
