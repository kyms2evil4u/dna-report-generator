# Deploy to Render

Render uses the `render.yaml` Blueprint to spin up the web service, Postgres, and Redis all at once.

---

## Steps

### 1. Push your repo to GitHub
Make sure `render.yaml` is at the repo root (or point Render to `deploy/render/render.yaml`).

### 2. Create a new Blueprint on Render
1. Go to [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint**
2. Connect your GitHub repo: `kyms2evil4u/dna-report-generator`
3. Render detects `render.yaml` automatically
4. Click **Apply** — it provisions web + Postgres + Redis together

### 3. Run the DB migration (first deploy only)
After the first deploy succeeds, open the Render shell for your web service and run:
```bash
# The init.sql runs automatically via docker-entrypoint on Postgres
# Nothing extra needed — Render's managed Postgres doesn't use init scripts
# Instead, connect and run manually:
psql $DATABASE_URL -f db/init.sql
```

Or use Render's **Shell** tab on the web service:
```bash
python -c "
from store import ReportStore
s = ReportStore()
print('Store initialized OK')
"
```

### 4. Custom domain (optional)
Dashboard → your web service → **Settings** → **Custom Domains** → add your domain → update DNS.

---

## Notes
- `generateValue: true` on `SECRET_KEY` means Render auto-creates a cryptographically secure value
- Free tier Postgres spins down after 90 days of inactivity — upgrade to "starter paid" for production
- To view logs: Dashboard → your service → **Logs** tab
- Auto-deploy: every push to `main` triggers a new deploy automatically
