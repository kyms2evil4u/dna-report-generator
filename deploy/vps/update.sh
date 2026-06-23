#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# DNA Report Generator — Zero-downtime update script
# Run on your VPS whenever you push new code to GitHub
#
# Usage: ./update.sh
# ─────────────────────────────────────────────────────────────────

set -euo pipefail

GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'; BOLD='\033[1m'
info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
info "App directory: $APP_DIR"

# 1. Pull latest code
info "Pulling latest code from GitHub..."
git -C "$APP_DIR" pull origin main
success "Code updated"

# 2. Rebuild only the web service (postgres + redis keep running)
info "Rebuilding web container..."
docker compose -f "$APP_DIR/docker-compose.yml" build web
success "Image rebuilt"

# 3. Rolling restart: bring up new container, then stop old one
info "Rolling restart (zero downtime)..."
docker compose -f "$APP_DIR/docker-compose.yml" up -d --no-deps web
success "Web service restarted"

# 4. Health check
sleep 5
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/api/health)
if [[ "$HTTP_STATUS" == "200" ]]; then
    success "Health check passed (HTTP $HTTP_STATUS)"
else
    echo -e "\033[0;31m[ERROR]\033[0m Health check failed (HTTP $HTTP_STATUS) — rolling back"
    docker compose -f "$APP_DIR/docker-compose.yml" restart web
    exit 1
fi

# 5. Clean up old images
info "Pruning dangling Docker images..."
docker image prune -f
success "Cleanup done"

echo ""
echo -e "${GREEN}${BOLD}✅  Update complete!${NC}"
