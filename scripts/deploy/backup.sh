#!/bin/bash
set -e

# =============================================================================
# moja-dzialka Backup Script
# Creates daily backups of all databases
# Usage: ./backup.sh [--full|--postgres|--neo4j|--mongo|--redis]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
BACKUP_DIR="${BACKUP_DIR:-/root/backups}"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=${RETENTION_DAYS:-7}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[BACKUP]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Load environment
cd "$PROJECT_DIR"
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Parse arguments
BACKUP_TYPE="${1:-full}"

log "=== Starting backup: $DATE (${BACKUP_TYPE}) ==="

backup_postgres() {
    log "Backing up PostgreSQL..."
    docker exec moja-dzialka-postgres pg_dump -U app moja_dzialka 2>/dev/null | gzip > "$BACKUP_DIR/postgres_$DATE.sql.gz"
    local size=$(ls -lh "$BACKUP_DIR/postgres_$DATE.sql.gz" | awk '{print $5}')
    log "  PostgreSQL backup: $size"
}

backup_neo4j() {
    log "Backing up Neo4j..."
    # Neo4j 5.x uses different backup command
    docker exec moja-dzialka-neo4j neo4j-admin database dump neo4j --to-stdout 2>/dev/null | gzip > "$BACKUP_DIR/neo4j_$DATE.dump.gz" || {
        # Fallback: copy data directory
        warn "neo4j-admin dump failed, using directory copy..."
        docker exec moja-dzialka-neo4j tar czf - /data 2>/dev/null > "$BACKUP_DIR/neo4j_data_$DATE.tar.gz"
    }
    local size=$(ls -lh "$BACKUP_DIR/neo4j"*"$DATE"* 2>/dev/null | tail -1 | awk '{print $5}')
    log "  Neo4j backup: $size"
}

backup_mongo() {
    log "Backing up MongoDB..."
    docker exec moja-dzialka-mongo mongodump --archive --gzip --db moja_dzialka 2>/dev/null > "$BACKUP_DIR/mongo_$DATE.archive.gz"
    local size=$(ls -lh "$BACKUP_DIR/mongo_$DATE.archive.gz" | awk '{print $5}')
    log "  MongoDB backup: $size"
}

backup_redis() {
    log "Backing up Redis..."
    # Trigger RDB save
    docker exec moja-dzialka-redis redis-cli BGSAVE >/dev/null 2>&1
    sleep 3
    # Copy RDB file
    docker cp moja-dzialka-redis:/data/dump.rdb "$BACKUP_DIR/redis_$DATE.rdb" 2>/dev/null || warn "Redis backup failed (may be empty)"
    if [ -f "$BACKUP_DIR/redis_$DATE.rdb" ]; then
        local size=$(ls -lh "$BACKUP_DIR/redis_$DATE.rdb" | awk '{print $5}')
        log "  Redis backup: $size"
    fi
}

backup_milvus() {
    log "Backing up Milvus..."
    # Milvus stores data in minio, backup the minio bucket
    docker exec moja-dzialka-minio mc alias set local http://localhost:9000 minioadmin minioadmin 2>/dev/null
    docker exec moja-dzialka-minio mc mirror local/milvus-bucket /tmp/milvus-backup 2>/dev/null
    docker exec moja-dzialka-minio tar czf - /tmp/milvus-backup 2>/dev/null > "$BACKUP_DIR/milvus_$DATE.tar.gz" || warn "Milvus backup failed"
    if [ -f "$BACKUP_DIR/milvus_$DATE.tar.gz" ]; then
        local size=$(ls -lh "$BACKUP_DIR/milvus_$DATE.tar.gz" | awk '{print $5}')
        log "  Milvus backup: $size"
    fi
}

# Execute backups based on type
case $BACKUP_TYPE in
    full)
        backup_postgres
        backup_neo4j
        backup_mongo
        backup_redis
        # backup_milvus  # Optional, embeddings can be regenerated
        ;;
    postgres)
        backup_postgres
        ;;
    neo4j)
        backup_neo4j
        ;;
    mongo)
        backup_mongo
        ;;
    redis)
        backup_redis
        ;;
    *)
        error "Unknown backup type: $BACKUP_TYPE"
        ;;
esac

# Cleanup old backups
log "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -type f -mtime +$RETENTION_DAYS -delete 2>/dev/null || true

# Summary
log "=== Backup complete ==="
log "Backup location: $BACKUP_DIR"
ls -lh "$BACKUP_DIR"/*"$DATE"* 2>/dev/null || warn "No backup files found for today"

# Calculate total size
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | awk '{print $1}')
log "Total backup size: $TOTAL_SIZE"

# Optional: sync to remote storage
# log "Syncing to S3..."
# aws s3 sync "$BACKUP_DIR" s3://moja-dzialka-backups/ --delete
