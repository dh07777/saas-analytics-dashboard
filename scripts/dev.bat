@echo off
start "InsightFlow API" cmd /k "cd backend && call .venv\Scripts\activate.bat && python run.py"
cd frontend
npm run dev
