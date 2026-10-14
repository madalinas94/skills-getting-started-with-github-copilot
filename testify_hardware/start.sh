#!/usr/bin/env bash
# Pornește aplicația Testify Hardware (macOS / Linux).
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Prima pornire: se instalează aplicația..."
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
