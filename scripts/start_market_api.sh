#!/bin/zsh
set -euo pipefail

ROOT="/Users/ersat/Desktop/Market_Gelsin"
VENV_PYTHON="$ROOT/.venv311/bin/python"
ENV_FILES=(
  "$ROOT/.env.market_gelsin_api.local"
  "$ROOT/.env.supabase.local"
  "$ROOT/.env.firebase.local"
)

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Python 3.11 venv bulunamadi: $VENV_PYTHON" >&2
  exit 1
fi

for ENV_FILE in "${ENV_FILES[@]}"; do
  if [[ -f "$ENV_FILE" ]]; then
    set -a
    source "$ENV_FILE"
    set +a
  fi
done

exec "$VENV_PYTHON" "$ROOT/api_server.py"
