#!/usr/bin/env bash
# Avvia SPECCHIO su http://localhost:8000
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r backend/requirements.txt
fi
if [ -f .env ]; then set -a; . ./.env; set +a; fi
cd backend
exec ../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
