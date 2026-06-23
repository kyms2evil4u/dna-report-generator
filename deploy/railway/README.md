# Deploy to Railway — Launch Guide

Railway auto-detects the `Dockerfile` and `railway.toml` at the repo root.
Total time to live URL: **~5 minutes**.

---

## One-Time Setup (do this once)

### 1. Create the Railway project
Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
→ select `kyms2evil4u/dna-report-generator` → click **Deploy Now**.

### 2. Add Postgres + Redis
In your Railway project dashboard:
- Click **+ New** → **Database** → **Add PostgreSQL**
- Click **+ New** → **Database** → **Add Redis**

Railway automatically injects `DATABASE_URL` and `REDIS_URL` into your service.

### 3. Set environment variables
In your service → **Variables** tab, add:

| Variable | Value |
|----------|-------|
| `SECRET_KEY` | run `openssl rand -hex 32` and paste the result |
| `FLASK_ENV` | `production` |
| `REPORT_TTL_DAYS` | `7` |

### 4. Get your Railway token (for CI auto-deploy)
Go to **Project Settings** → **Tokens** → **New Token** → copy it.

Add it to GitHub: repo → **Settings → Secrets → Actions → New secret**
- Name: `RAILWAY_TOKEN`
- Value: your token

### 5. That's it — every push to `main` auto-deploys ✅

---

## Useful CLI commands
```bash
npm install -g @railway/cli
railway login
railway logs          # tail live logs
railway run python main.py formats   # run a one-off command
railway open          # open your live URL
```

## Health check
Your app exposes `GET /api/health` — Railway monitors this automatically.
