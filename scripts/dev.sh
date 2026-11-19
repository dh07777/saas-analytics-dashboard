#!/usr/bin/env bash
# Starts API (5000) and web app (5173). Ctrl+C stops both.
(cd backend && . .venv/bin/activate && python run.py) &
API=$!
trap "kill $API" EXIT
cd frontend && npm run dev
