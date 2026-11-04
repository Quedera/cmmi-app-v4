#!/bin/bash
# Pulse v4 backend entrypoint — seeds the DB from the baked-in initial state
# if the Azure Files mount is empty, then execs the CMD (uvicorn).
# Mirrors the cmmi-app pattern but uses cmmi_v4.sqlite as the seed name.
set -e

mkdir -p /app/data

DB=/app/data/cmmi_v4.sqlite

if [ ! -f "$DB" ]; then
  echo "[entrypoint] Seeding database from /app/seed/cmmi_v4.sqlite"
  cp /app/seed/cmmi_v4.sqlite "$DB"
fi

# The Azure Files mount persists across container revisions, so a database
# seeded by an older image keeps its old schema (missing respondent_role
# column, mangled discipline names). Apply pending migrations on every
# start-up; both scripts are idempotent (name/PRAGMA guarded) so re-runs
# are no-ops.
for m in 014_clean_discipline_names 015_add_respondent_metadata 016_DEF-019_remove_duplicate_no; do
  script="/app/backend/migrations/$m.py"
  if [ -f "$script" ]; then
    echo "[entrypoint] Applying $m"
    python3 "$script" "$DB" || echo "[entrypoint] WARNING: $m failed - continuing"
  fi
done

exec "$@"