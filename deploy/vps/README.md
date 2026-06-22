# Deploy to a VPS (Ubuntu 22.04/24.04)

Full production setup with Docker, Nginx, Let's Encrypt TLS, and systemd auto-start.
Works on any VPS provider: DigitalOcean, Hetzner, Linode, AWS EC2, etc.

**Recommended specs:** 2 vCPU / 2GB RAM / 20GB SSD (~$6–12/mo on Hetzner or DigitalOcean)

---

## One-command setup

```bash
# 1. SSH into your server
ssh root@YOUR_SERVER_IP

# 2. Download and run the setup script
curl -fsSL https://raw.githubusercontent.com/kyms2evil4u/dna-report-generator/main/deploy/vps/setup.sh -o setup.sh
chmod +x setup.sh
sudo ./setup.sh
```

The script will prompt you for:
- Your domain name (e.g. `dna.yourdomain.com`)
- Your email (for Let's Encrypt expiry notices)
- The Linux user to run the service under

Everything else is automated.

---

## What the script does

| Step | Action |
|---|---|
| 1 | Updates system packages, installs Docker + Nginx + Certbot |
| 2 | Configures UFW firewall (SSH + 80 + 443 only) |
| 3 | Clones the GitHub repo |
| 4 | Auto-generates `SECRET_KEY` and `POSTGRES_PASSWORD` |
| 5 | Starts the full Docker Compose stack |
| 6 | Configures Nginx as a reverse proxy |
| 7 | Issues a free Let's Encrypt TLS certificate |
| 8 | Adds certbot auto-renewal cron job |
| 9 | Creates a systemd service (auto-starts on reboot) |

---

## DNS Setup

Before running setup, point your domain's A record to your server IP:

```
A    dna.yourdomain.com    →    YOUR_SERVER_IP    TTL: 300
```

Wait 5 minutes for DNS to propagate, then run the script.

---

## Updating after a code push

```bash
ssh user@YOUR_SERVER_IP
cd ~/dna-report-generator
./deploy/vps/update.sh
```

The update script does a rolling restart — Postgres and Redis stay running, only the web container is rebuilt. Includes a health check with automatic rollback if the new container fails.

---

## Useful commands

```bash
# View live logs
docker compose logs -f web

# Restart the stack
systemctl restart dna-report

# Check service status
systemctl status dna-report

# Connect to Postgres directly
docker compose exec postgres psql -U dna_user -d dna_reports

# Connect to Redis
docker compose exec redis redis-cli

# Check disk usage
docker system df
```

---

## Recommended VPS providers

| Provider | Cheapest plan | Notes |
|---|---|---|
| [Hetzner](https://hetzner.com/cloud) | €4.15/mo (CX22, 2vCPU/4GB) | Best price/performance in EU |
| [DigitalOcean](https://digitalocean.com) | $6/mo (Basic, 1vCPU/1GB) | Good docs, easy snapshots |
| [Linode/Akamai](https://linode.com) | $5/mo (Nanode, 1vCPU/1GB) | Reliable, good network |
| [Vultr](https://vultr.com) | $5/mo (1vCPU/1GB) | Many regions |
