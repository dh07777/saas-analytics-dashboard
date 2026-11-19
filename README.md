# InsightFlow: Smart Business Analytics Platform

A full-stack SaaS analytics dashboard. **Flask + SQLAlchemy + SQLite** backend, **React (Vite) + Recharts** frontend.
Every number on screen is calculated from database records. Nothing is hardcoded.

## Features
- JWT auth: register, login, logout (token revocation), forgot/reset password, change password, session-expiry handling
- 5 roles with a permissions table: Super Admin, Business Admin, Manager, Analyst, Standard User
- Dashboard (KPIs, trends, top products, recent transactions/activity, customizable widgets)
- Revenue analytics (daily/weekly/monthly/yearly, period comparison, profit, linear-trend forecast with range)
- Customer analytics (new/returning, retention, segments, lifetime value, growth) and customer CRUD
- Sales analytics (category/product/region, trends, comparison) and order management (create, complete, cancel, refund, delete; stock and transactions update)
- Product analytics (best/low performers, inventory, restock list) with product and category CRUD
- Expense CRUD plus monthly profit & loss
- Reports center: 5 report types, custom dates, CSV and PDF export, print, history
- Transactions ledger (sales/refunds, filters, totals) and order detail view
- Audit log page for business admins
- Super Admin: view any business from the top-bar switcher, edit role permissions live (Admin > Roles & permissions)
- Notifications (low stock, revenue changes, team activity; polled every 30 s)
- User management, settings (company, currency, date format, theme, notification prefs), admin panel (system overview, businesses, database stats, audit logs, activity, runtime config)
- Sample data is flagged `is_sample` on every row, shown with a banner, and removable from Settings without touching live data

## Quick start (scripts)
- Windows: `scripts\setup.bat` once, then `scripts\dev.bat`
- macOS/Linux: `bash scripts/setup.sh` once, then `bash scripts/dev.sh`

In VS Code you can also use *Terminal > Run Task* (install, seed, run both, tests) and the *Flask API (debug)* launch configuration (F5). Accept the recommended extensions when prompted.

## Run locally in VS Code (step by step)

**Prerequisites:** Python 3.11+, Node.js 18+ (20 recommended), VS Code. Recommended extensions: *Python*, *ES7+ React snippets* (optional).

1. **Open the project.** VS Code > File > Open Folder > select the `insightflow` folder.
2. **Open a terminal** (Terminal > New Terminal). You will use two terminals: one for the backend, one for the frontend.

### Backend (terminal 1)
```bash
cd backend
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# Windows (cmd):         .venv\Scripts\activate.bat
# macOS / Linux:         source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
python smoke_test.py            # optional: checks login and every API endpoint against a temporary DB
python run.py                   # API on http://127.0.0.1:5000 (first start creates the DB and loads sample data automatically)
```
If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` first.
In VS Code press `Ctrl+Shift+P` > *Python: Select Interpreter* > choose `backend/.venv`.

The first start in development creates the tables and loads ~120 customers, 64 products, 400 orders and expenses (a few seconds). Set `AUTO_SEED=false` in `.env` to skip that. `flask --app run seed --reset` rebuilds the sample data.

Check it works: open http://127.0.0.1:5000/api/health, which should show `{"status":"ok"}`.

### Frontend (terminal 2)
```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```
Open http://localhost:5173 and sign in with a demo account (password `Demo@1234`):

| Email | Role |
|---|---|
| admin@insightflow.demo | Business Admin |
| manager@insightflow.demo | Manager |
| analyst@insightflow.demo | Analyst |
| user@insightflow.demo | Standard User |
| super@insightflow.demo | Super Admin (admin panel) |

Vite proxies `/api` to Flask, so no CORS setup is needed in development.

### Forgot password in development
No email server is configured. The forgot-password page shows the reset link directly when `APP_ENV=development`. In production the link is only written to the server log; connect an email provider before real use.

### Start with an empty (real) database instead of sample data
```bash
flask --app run create-superadmin     # prompts for email, name, password
```
Or register a new account in the UI: it creates a fresh, empty business.

## Troubleshooting
- **Blank page:** keep the backend running, then press `F12` > Console in the browser. The app now shows the error text on screen instead of staying blank; send that text for a fix.
- **"Backend is not reachable" on the sign-in page:** start the backend (`python run.py` in `backend`) and keep that terminal open. It must listen on port 5000.
- **Incorrect email or password:** use `admin@insightflow.demo` / `Demo@1234`. If you changed data, run `flask --app run seed --reset`.
- **`pip install` fails:** use Python 3.11 or 3.12 (3.13 works with the current requirements but 3.12 is the safest).
- **Port in use:** stop the other program, or change the port in `run.py` and in `frontend/vite.config.js`.

## Tests
```bash
cd backend && pytest            # auth, RBAC, models, analytics vs DB, CRUD, reports, tenant isolation
cd frontend && npm test         # component and helper tests (Vitest)
```

## Database migrations (Flask-Migrate)
`flask --app run seed` uses `create_all()` for a quick start. To track schema changes afterwards:
```bash
flask --app run db init && flask --app run db migrate -m "initial" && flask --app run db upgrade
```

## Production deployment
**Backend** (any Linux host or PaaS that keeps a persistent disk, since SQLite is a file):
1. Set environment variables: `APP_ENV=production`, strong random `SECRET_KEY` and `JWT_SECRET_KEY` (`python -c "import secrets;print(secrets.token_urlsafe(48))"`), `CORS_ORIGINS=https://your-frontend-domain`, `DATABASE_URL=sqlite:////var/data/insightflow.db` (absolute path on a persistent volume).
2. `pip install -r requirements.txt && flask --app wsgi init-db`
3. Run with `gunicorn -w 2 -b 0.0.0.0:5000 wsgi:app` (Linux) or `waitress-serve --port=5000 wsgi:app` (Windows). Put Nginx/Caddy with HTTPS in front.
4. Back up the `.db` file regularly. The app refuses to start in production with default secrets.

Use a single worker group on one machine: the rate limiter is in-memory per process, and SQLite handles one writer at a time.

**Frontend:** `cd frontend && VITE_API_URL=https://your-api-domain/api npm run build`, then upload `frontend/dist` to any static host (Netlify, Vercel, Cloudflare Pages, Nginx). `netlify.toml` and `vercel.json` already rewrite all paths to `index.html`. `deploy/` has an Nginx config and a systemd service for the API.

## Project structure
```
backend/  app/{models,utils,services,seed}.py  app/routes/{auth,analytics,data,users,misc,reports,admin}.py  tests/
frontend/ src/{api,contexts,hooks,components,pages,utils,__tests__}
```

## Security notes
Password hashing (Werkzeug), JWT with server-side revocation on logout, role/permission checks on every endpoint, per-business data isolation, input validation, parameterized queries (SQLAlchemy), CSV formula-injection guard, rate limiting (global and on auth endpoints), CORS allow-list, security headers, audit log, secrets from environment.

## Known limitations
- SQLite and the in-memory rate limiter suit a single server, not horizontal scaling.
- Notifications are polled, not pushed (WebSockets would be the next step).
- No email delivery (see forgot-password note). The forecast is a simple linear trend, shown with its error range.
