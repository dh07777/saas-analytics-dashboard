#!/usr/bin/env bash
# One-time setup for macOS / Linux. Run from the project root: bash scripts/setup.sh
set -e
cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
flask --app run seed
cd ../frontend && npm install
echo "Done. Start with: bash scripts/dev.sh"
