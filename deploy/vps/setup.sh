#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# DNA Report Generator — VPS Bootstrap Script
# Tested on: Ubuntu 22.04 / 24.04 LTS
#
# What this does:
#   1. Installs Docker, Docker Compose, Nginx, Certbot
#   2. Clones the repo
#   3. Creates .env from your inputs
#   4. Starts the Docker stack
#   5. Configures Nginx as a reverse proxy
#   6. Issues a free Let's Encrypt TLS certificate
#
# Usage:
#   chmod +x setup.sh
#   sudo ./setup.sh
# ─────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Colors ───────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

echo -e "\n${BOLD}🧬 DNA Report Generator — VPS Setup${NC}\n"

# ── Root check ───────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && error "Run this script as root: sudo ./setup.sh"

# ── Gather config ─────────────────────────────────────────────────
read -rp "$(echo -e "${BOLD}Domain name${NC} (e.g. dna.yourdomain.com): ")" DOMAIN
read -rp "$(echo -e "${BOLD}Email for Let's Encrypt${NC}: ")" LE_EMAIL
read -rp "$(echo -e "${BOLD}App user to run service${NC} [default: ubuntu]: ")" APP_USER
APP_USER=${APP_USER:-ubuntu}
APP_DIR="/home/${APP_USER}/dna-report-generator"

POSTGRES_PASSWORD=$(openssl rand -hex 20)
SECRET_KEY=$(openssl rand -hex 32)

info "Domain:   $DOMAIN"
info "App dir:  $APP_DIR"
info "App user: $APP_USER"
echo ""

# ── 1. System update ─────────────────────────────────────────────
info "Updating system packages..."
apt-get update -qq && apt-get upgrade -y -qq
apt-get install -y -qq curl git openssl ufw fail2ban
success "System updated"

# ── 2. Docker ────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    info "Installing Docker..."
    curl -fsSL https://get.docker.com | bash
    usermod -aG docker "$APP_USER"
    success "Docker installed"
else
    success "Docker already installed ($(docker --version))"
fi

# Docker Compose v2
if ! docker compose version &>/dev/null 2>&1; then
    info "Installing Docker Compose plugin..."
    apt-get install -y -qq docker-compose-plugin
    success "Docker Compose installed"
else
    success "Docker Compose already installed"
fi

# ── 3. Nginx + Certbot ───────────────────────────────────────────
info "Installing Nginx and Certbot..."
apt-get install -y -qq nginx certbot python3-certbot-nginx
systemctl enable nginx
success "Nginx and Certbot installed"

# ── 4. Firewall ──────────────────────────────────────────────────
info "Configuring UFW firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
success "Firewall configured (SSH + HTTP + HTTPS)"

# ── 5. Clone repo ─────────────────────────────────────────────────
info "Cloning repository to $APP_DIR..."
if [[ -d "$APP_DIR" ]]; then
    warn "Directory exists — pulling latest changes"
    sudo -u "$APP_USER" git -C "$APP_DIR" pull
else
    sudo -u "$APP_USER" git clone https://github.com/kyms2evil4u/dna-report-generator.git "$APP_DIR"
fi
success "Repository ready"

# ── 6. Create .env ───────────────────────────────────────────────
info "Creating .env file..."
cat > "$APP_DIR/.env" << EOF
SECRET_KEY=${SECRET_KEY}
FLASK_ENV=production
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
HOST_PORT=5000
REPORT_TTL_DAYS=7
EOF
chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
chmod 600 "$APP_DIR/.env"
success ".env created (passwords auto-generated)"

# ── 7. Start Docker stack ─────────────────────────────────────────
info "Building and starting Docker services..."
cd "$APP_DIR"
sudo -u "$APP_USER" docker compose pull
sudo -u "$APP_USER" docker compose up -d --build
success "Docker stack started"

# ── 8. Nginx reverse proxy config ────────────────────────────────
info "Writing Nginx server block for $DOMAIN..."
cat > "/etc/nginx/sites-available/dna-report" << NGINXCONF
server {
    listen 80;
    server_name ${DOMAIN};
    client_max_body_size 100M;

    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
NGINXCONF

ln -sf /etc/nginx/sites-available/dna-report /etc/nginx/sites-enabled/dna-report
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
success "Nginx configured for $DOMAIN"

# ── 9. TLS Certificate ───────────────────────────────────────────
info "Issuing Let's Encrypt certificate for $DOMAIN..."
certbot --nginx \
    --non-interactive \
    --agree-tos \
    --email "$LE_EMAIL" \
    --domains "$DOMAIN" \
    --redirect   # auto-redirect HTTP → HTTPS
success "TLS certificate issued and HTTPS configured"

# ── 10. Auto-renew cron ───────────────────────────────────────────
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && systemctl reload nginx") | crontab -
success "Certbot auto-renewal cron job added"

# ── 11. Systemd service (auto-start on reboot) ────────────────────
info "Creating systemd service for Docker stack..."
cat > /etc/systemd/system/dna-report.service << SVCEOF
[Unit]
Description=DNA Report Generator Docker Stack
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${APP_DIR}
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=300
User=${APP_USER}

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable dna-report.service
success "Systemd service enabled (auto-starts on reboot)"

# ── Done ──────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✅  Setup Complete!${NC}"
echo -e "${GREEN}${BOLD}════════════════════════════════════════════${NC}"
echo ""
echo -e "  🌐  App URL:      ${BOLD}https://${DOMAIN}${NC}"
echo -e "  📁  App dir:      ${BOLD}${APP_DIR}${NC}"
echo -e "  🐳  Docker logs:  ${BOLD}docker compose -C ${APP_DIR} logs -f web${NC}"
echo -e "  📋  Systemd:      ${BOLD}systemctl status dna-report${NC}"
echo ""
echo -e "${YELLOW}  Save these credentials somewhere safe:${NC}"
echo -e "  Postgres password: ${BOLD}${POSTGRES_PASSWORD}${NC}"
echo -e "  Secret key:        ${BOLD}${SECRET_KEY}${NC}"
echo ""
