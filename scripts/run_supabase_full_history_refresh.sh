#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

for env_file in \
  "$ROOT_DIR/.env.market_gelsin_api.local" \
  "$ROOT_DIR/.env.supabase.local" \
  "$ROOT_DIR/.env.firebase.local"
do
  if [ -f "$env_file" ]; then
    # shellcheck disable=SC1090
    source "$env_file"
  fi
done

export MARKET_GELSIN_MIGRATION_PROFILE=full_history

python3 "$ROOT_DIR/scripts/migrate_live_subset_to_postgres.py"
python3 "$ROOT_DIR/scripts/apply_supabase_barkod_read_model.py"
