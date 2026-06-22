# Deploy to Railway

Railway auto-detects the Dockerfile and provisions managed Postgres + Redis for you.
Total time: ~5 minutes.

---

## Steps

### 1. Install Railway CLI
```bash
npm install -g @railway/cli
railway login
```

### 2. Create project & link repo
```bash
railway init
# Select "Empty Project", name it "dna-report-generator"

railway link
# Select your project
```

### 3. Add Postgres + Redis plugins
In the Railway dashboard → your project → **+ New** → select **PostgreSQL**, then **+ New** → **Redis**.

Or via CLI:
```bash
railway add --plugin postgresql
railway add --plugin redis
```

### 4. Set environment variables
```bash
railway variables set SECRET_KEY=$(openssl rand -hex 32)
railway variables set FLASK_ENV=production
railway variables set REPORT_TTL_DAYS=7
```

Railway automatically injects `DATABASE_URL` and `REDIS_URL` from the plugins — no manual wiring needed.

### 5. Deploy
```bash
railway up
```

### 6. Open your app
```bash
railway open
```

---

## Notes
- Railway runs the `Dockerfile` automatically — no config changes needed.
- The `railway.toml` in this folder sets the health check path and restart policy.
- To view logs: `railway logs`
- To run a one-off command (e.g. DB migration): `railway run python main.py formats`
