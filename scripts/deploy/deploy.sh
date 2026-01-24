#!/bin/bash
set -e

# =============================================================================
# moja-dzialka Deployment Script
# Usage: ./deploy.sh [--full|--backend|--frontend]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Parse arguments
DEPLOY_TYPE="${1:-full}"

log "=== Deploying moja-dzialka (${DEPLOY_TYPE}) ==="
log "Project dir: $PROJECT_DIR"

# Pull latest code
log "Pulling latest code from git..."
git pull origin main || warn "Git pull failed, continuing with local code"

# Load environment
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    error ".env file not found!"
fi

# Deploy based on type
case $DEPLOY_TYPE in
    full)
        log "Full deployment: rebuilding all services..."
        docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache
        docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
        ;;
    backend)
        log "Backend deployment..."
        docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache backend celery-worker
        docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend celery-worker
        ;;
    frontend)
        log "Frontend deployment..."
        docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache frontend
        docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d frontend
        ;;
    restart)
        log "Restarting services (no rebuild)..."
        docker compose -f docker-compose.yml -f docker-compose.prod.yml restart
        ;;
    *)
        error "Unknown deploy type: $DEPLOY_TYPE"
        ;;
esac

# Wait for services
log "Waiting for services to start..."
sleep 15

# Health check
log "Running health check..."
HEALTH_URL="http://localhost:8000/health"
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL || echo "000")

if [ "$HEALTH_STATUS" = "200" ]; then
    log "Health check passed!"
else
    warn "Health check returned: $HEALTH_STATUS"
fi

# Show status
log "=== Deployment complete ==="
docker compose ps

# Show resource usage
log "Resource usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | head -15
