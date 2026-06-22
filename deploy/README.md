# Deployment Guide

Three production-ready deployment paths — pick whichever fits your needs.

---

## Option Comparison

| | Railway | Render | VPS |
|---|---|---|---|
| **Setup time** | ~5 min | ~5 min | ~10 min |
| **Cost** | ~$5–20/mo | Free tier → $7/mo | $4–12/mo |
| **Managed Postgres** | ✅ | ✅ | Docker (self-managed) |
| **Managed Redis** | ✅ | ✅ | Docker (self-managed) |
| **Auto-deploy on push** | ✅ | ✅ | Via `update.sh` |
| **Custom domain + TLS** | ✅ | ✅ | ✅ (Let's Encrypt) |
| **Full control** | ❌ | ❌ | ✅ |
| **Best for** | Fast start | Free tier | Full control / cheapest |

---

## Quick links

- 🚂 **[Railway →](./railway/README.md)** — easiest, CLI-driven, managed everything
- 🎨 **[Render →](./render/README.md)** — Blueprint YAML, generous free tier
- 🖥️ **[VPS →](./vps/README.md)** — one script, Ubuntu 22.04, certbot TLS, systemd

---

## Environment variables (all platforms)

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | Flask session secret — use `openssl rand -hex 32` |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `REDIS_URL` | ✅ | Redis connection string |
| `FLASK_ENV` | ✅ | Set to `production` |
| `REPORT_TTL_DAYS` | ❌ | Days before reports auto-expire (default: 7) |
| `NCBI_API_KEY` | ❌ | Raises ClinVar rate limit from 3→10 req/sec |
| `PORT` | ❌ | Default: 5000 |
