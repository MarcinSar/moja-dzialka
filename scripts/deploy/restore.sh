#!/bin/bash
set -e

# =============================================================================
# moja-dzialka Restore Script
# Restores databases from backup
# Usage: ./restore.sh <backup_date> [--postgres|--neo4j|--mongo|--redis|--all]
# Example: ./restore.sh 20260124_030000 --all
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
BACKUP_DIR="${BACKUP_DIR:-/root/backups}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[RESTORE]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check arguments
if [ -z "$1" ]; then
    echo "Usage: ./restore.sh <backup_date> [--postgres|--neo4j|--mongo|--redis|--all]"
    echo "Example: ./restore.sh 20260124_030000 --all"
    echo ""
    echo "Available backups:"
    ls -la "$BACKUP_DIR"/*.gz 2>/dev/null | tail -10
    exit 1
fi

DATE=$1
RESTORE_TYPE="${2:---all}"

# Verify backup files exist
verify_backup() {
    local type=$1
    local file="$BACKUP_DIR/${type}_$DATE"*
    if ! ls $file 1>/dev/null 2>&1; then
        error "Backup file not found: $file"
    fi
}

# Load environment
cd "$PROJECT_DIR"
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

log "=== Restoring from backup: $DATE ==="
warn "This will OVERWRITE existing data. Press Ctrl+C to cancel."
sleep 5

restore_postgres() {
    verify_backup "postgres"
    log "Restoring PostgreSQL..."

    # Stop backend to prevent writes
    docker compose stop backend celery-worker 2>/dev/null || true

    # Drop and recreate database
    docker exec moja-dzialka-postgres psql -U app -c "DROP DATABASE IF EXISTS moja_dzialka;" postgres 2>/dev/null || true
    docker exec moja-dzialka-postgres psql -U app -c "CREATE DATABASE moja_dzialka;" postgres

    # Restore
    gunzip -c "$BACKUP_DIR/postgres_$DATE.sql.gz" | docker exec -i moja-dzialka-postgres psql -U app moja_dzialka

    log "  PostgreSQL restored!"
}

restore_neo4j() {
    verify_backup "neo4j"
    log "Restoring Neo4j..."

    # Stop neo4j
    docker compose stop neo4j

    # Check backup type (dump vs tar)
    if [ -f "$BACKUP_DIR/neo4j_$DATE.dump.gz" ]; then
        # Restore from dump
        gunzip -c "$BACKUP_DIR/neo4j_$DATE.dump.gz" | docker exec -i moja-dzialka-neo4j neo4j-admin database load neo4j --from-stdin --overwrite-destination=true
    elif [ -f "$BACKUP_DIR/neo4j_data_$DATE.tar.gz" ]; then
        # Restore from tar
        docker exec moja-dzialka-neo4j rm -rf /data/*
        docker exec -i moja-dzialka-neo4j tar xzf - -C / < "$BACKUP_DIR/neo4j_data_$DATE.tar.gz"
    fi

    # Start neo4j
    docker compose start neo4j

    log "  Neo4j restored!"
}

restore_mongo() {
    verify_backup "mongo"
    log "Restoring MongoDB..."

    # Drop existing database
    docker exec moja-dzialka-mongo mongosh moja_dzialka --eval "db.dropDatabase()" 2>/dev/null || true

    # Restore
    docker exec -i moja-dzialka-mongo mongorestore --archive --gzip --drop < "$BACKUP_DIR/mongo_$DATE.archive.gz"

    log "  MongoDB restored!"
}

restore_redis() {
    if [ ! -f "$BACKUP_DIR/redis_$DATE.rdb" ]; then
        warn "Redis backup not found, skipping..."
        return
    fi

    log "Restoring Redis..."

    # Stop redis
    docker compose stop redis

    # Copy RDB file
    docker cp "$BACKUP_DIR/redis_$DATE.rdb" moja-dzialka-redis:/data/dump.rdb

    # Start redis
    docker compose start redis

    log "  Redis restored!"
}

# Execute restore based on type
case $RESTORE_TYPE in
    --all)
        restore_postgres
        restore_neo4j
        restore_mongo
        restore_redis
        ;;
    --postgres)
        restore_postgres
        ;;
    --neo4j)
        restore_neo4j
        ;;
    --mongo)
        restore_mongo
        ;;
    --redis)
        restore_redis
        ;;
    *)
        error "Unknown restore type: $RESTORE_TYPE"
        ;;
esac

# Restart services
log "Restarting services..."
docker compose start backend celery-worker 2>/dev/null || true

# Health check
log "Running health check..."
sleep 10
curl -s http://localhost:8000/health | head -c 100 || warn "Health check failed"

log "=== Restore complete ==="
