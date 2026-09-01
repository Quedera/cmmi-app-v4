#!/bin/bash
# Pulse v4 backend entrypoint — seeds the DB from the baked-in initial state
# if the Azure Files mount is empty, then execs the CMD (uvicorn).
# Mirrors the cmmi-app pattern but uses cmmi_v4.sqlite as the seed name.
set -e

mkdir -p /app/data

if [ ! -f /app/data/cmmi_v4.sqlite ]; then
  echo "[entrypoint] Seeding database from /app/seed/cmmi_v4.sqlite"
  cp /app/seed/cmmi_v4.sqlite /app/data/cmmi_v4.sqlite
fi

exec "$@"