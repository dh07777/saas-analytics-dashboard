@echo off
REM One-time setup for Windows. Run from the project root: scripts\setup.bat
cd backend
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt
if not exist .env copy .env.example .env
flask --app run seed
cd ..\frontend
call npm install
echo Done. Start with: scripts\dev.bat
