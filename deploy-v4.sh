#!/usr/bin/env bash
# deploy-v4.sh — restart Pulse v4 services and (optionally) apply DB migrations.
#
# Pulse v4 runs on the miniPC (openclaw130) via systemd, NOT Azure. The
# cmmi-app/ directory has the Azure/Docker setup; v4 stays local for now.
#
# Usage:
#   ./deploy-v4.sh                       # code-only restart
#   ./deploy-v4.sh --with-migrations     # also run any pending migrations
#
# Migrations applied (in order):
#   - 014_clean_discipline_names.py  (Pulse release)
#
# Healthcheck ports:
#   - Backend  :8003
#   - Frontend :5558

set -euo pipefail

WORKDIR="/home/nortski101/.openclaw/workspace/cmmi-app-v4"
DB_PATH="${WORKDIR}/cmmi_v4.sqlite"
MIGRATIONS_DIR="${WORKDIR}/backend/migrations"
BACKEND_SVC="cmmi-v4-backend.service"
FRONTEND_SVC="cmmi-v4-frontend.service"

WITH_MIGRATIONS=0
if [[ "${1:-}" == "--with-migrations" ]]; then
  WITH_MIGRATIONS=1
fi

run_migration_014() {
  local script="${MIGRATIONS_DIR}/014_clean_discipline_names.py"
  if [[ ! -f "${script}" ]]; then
    echo "ERROR: migration script not found: ${script}" >&2
    exit 1
  fi
  echo "==> Running 014_clean_discipline_names.py against ${DB_PATH}"
  python3 "${script}" "${DB_PATH}"
}

echo "==> Restarting ${BACKEND_SVC}"
sudo systemctl restart "${BACKEND_SVC}"
echo "==> Restarting ${FRONTEND_SVC}"
sudo systemctl restart "${FRONTEND_SVC}"

if [[ "${WITH_MIGRATIONS}" -eq 1 ]]; then
  echo "==> Stopping ${BACKEND_SVC} (DB must be unlocked)"
  sudo systemctl stop "${BACKEND_SVC}"
  run_migration_014
  echo "==> Starting ${BACKEND_SVC}"
  sudo systemctl start "${BACKEND_SVC}"
fi

# Give services a moment to bind
sleep 2

echo "==> Health check"
echo -n "  backend  :8003 → "
if curl -fsS --max-time 5 http://localhost:8003/health > /dev/null; then
  echo "OK"
else
  echo "FAILED"
  sudo systemctl status "${BACKEND_SVC}" --no-pager | tail -20
  exit 1
fi

echo -n "  frontend :5558 → "
if curl -fsSL --max-time 5 -A "Mozilla/5.0" http://localhost:5558/ > /dev/null; then
  echo "OK"
else
  echo "FAILED"
  sudo systemctl status "${FRONTEND_SVC}" --no-pager | tail -20
  exit 1
fi

echo
echo "==> Deploy complete."