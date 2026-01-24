#!/bin/bash
set -e

# =============================================================================
# moja-dzialka Initial Data Import Script
# Imports processed data into all databases
# Usage: ./import-data.sh [--postgis|--neo4j|--milvus|--all]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
DATA_DIR="$PROJECT_DIR/data/ready-for-import"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${GREEN}[IMPORT]${NC} $1"; }
info() { echo -e "${CYAN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Load environment
cd "$PROJECT_DIR"
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-secret}"

# Parse arguments
IMPORT_TYPE="${1:---all}"

log "=== moja-dzialka Data Import ==="
log "Data directory: $DATA_DIR"

# Verify data exists
if [ ! -d "$DATA_DIR/postgis" ]; then
    error "Data directory not found: $DATA_DIR/postgis"
fi

# Check if databases are running
check_databases() {
    log "Checking database connections..."

    # PostgreSQL
    docker exec moja-dzialka-postgres pg_isready -U app -d moja_dzialka >/dev/null 2>&1 || {
        error "PostgreSQL is not ready. Start with: docker compose up -d postgres"
    }
    info "  PostgreSQL: OK"

    # Neo4j
    curl -s http://localhost:7474 >/dev/null 2>&1 || {
        warn "Neo4j may not be ready yet"
    }
    info "  Neo4j: checking..."

    # Milvus
    curl -s http://localhost:19530/healthz >/dev/null 2>&1 || {
        warn "Milvus may not be ready yet"
    }
    info "  Milvus: checking..."
}

import_postgis() {
    log "=== Importing to PostGIS ==="

    # Check if ogr2ogr is available
    if ! command -v ogr2ogr &> /dev/null; then
        # Use docker with GDAL
        OGR_CMD="docker run --rm --network host -v $DATA_DIR:/data osgeo/gdal:alpine-small-3.6.4 ogr2ogr"
    else
        OGR_CMD="ogr2ogr"
    fi

    PG_CONN="PG:host=localhost port=5432 dbname=moja_dzialka user=app password=$POSTGRES_PASSWORD"

    # Import each GPKG file
    for gpkg in "$DATA_DIR/postgis"/*.gpkg; do
        if [ -f "$gpkg" ]; then
            table=$(basename "$gpkg" .gpkg)
            info "Importing: $table"

            if [ "$OGR_CMD" = "ogr2ogr" ]; then
                ogr2ogr -f "PostgreSQL" "$PG_CONN" "$gpkg" -nln "$table" -overwrite -progress 2>&1 | tail -1
            else
                # Docker version needs different path
                filename=$(basename "$gpkg")
                docker run --rm --network host \
                    -v "$DATA_DIR/postgis:/data" \
                    osgeo/gdal:alpine-small-3.6.4 \
                    ogr2ogr -f "PostgreSQL" "$PG_CONN" "/data/$filename" -nln "$table" -overwrite
            fi
        fi
    done

    # Create spatial indexes
    log "Creating spatial indexes..."
    docker exec moja-dzialka-postgres psql -U app moja_dzialka -c "
        CREATE INDEX IF NOT EXISTS idx_parcels_enriched_geom ON parcels_enriched USING GIST (geom);
        CREATE INDEX IF NOT EXISTS idx_pog_trojmiasto_geom ON pog_trojmiasto USING GIST (geom);
        CREATE INDEX IF NOT EXISTS idx_poi_trojmiasto_geom ON poi_trojmiasto USING GIST (geom);
        CREATE INDEX IF NOT EXISTS idx_budynki_geom ON budynki USING GIST (geom);
    " 2>/dev/null || warn "Some indexes may already exist"

    # Verify import
    log "Verifying PostGIS import..."
    docker exec moja-dzialka-postgres psql -U app moja_dzialka -c "
        SELECT table_name,
               (xpath('//rowcount/text()', xml_count))[1]::text::int as row_count
        FROM (
            SELECT table_name,
                   query_to_xml('SELECT COUNT(*) as rowcount FROM ' || table_name, false, false, '')::text::xml as xml_count
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        ) t;
    " 2>/dev/null || docker exec moja-dzialka-postgres psql -U app moja_dzialka -c "\dt"

    log "PostGIS import complete!"
}

import_neo4j() {
    log "=== Importing to Neo4j ==="

    # Check if import script exists
    IMPORT_SCRIPT="$PROJECT_DIR/egib/scripts/pipeline/08_import_neo4j.py"

    if [ -f "$IMPORT_SCRIPT" ]; then
        info "Running Neo4j import script..."
        cd "$PROJECT_DIR"
        python3 "$IMPORT_SCRIPT" || {
            warn "Neo4j import script failed. You may need to create it."
            warn "Skipping Neo4j import for now."
        }
    else
        warn "Neo4j import script not found: $IMPORT_SCRIPT"
        warn "Please create the script or import manually."
        info "Expected data files in: $DATA_DIR/neo4j/"
        ls -la "$DATA_DIR/neo4j/" 2>/dev/null || true
    fi

    log "Neo4j import complete (or skipped)!"
}

import_milvus() {
    log "=== Importing to Milvus ==="

    # Check if embedding/import scripts exist
    EMBED_SCRIPT="$PROJECT_DIR/egib/scripts/pipeline/09_generate_embeddings.py"
    IMPORT_SCRIPT="$PROJECT_DIR/egib/scripts/pipeline/10_import_milvus.py"

    if [ -f "$EMBED_SCRIPT" ] && [ -f "$IMPORT_SCRIPT" ]; then
        info "Generating embeddings..."
        cd "$PROJECT_DIR"
        python3 "$EMBED_SCRIPT" || warn "Embedding generation failed"

        info "Importing to Milvus..."
        python3 "$IMPORT_SCRIPT" || warn "Milvus import failed"
    else
        warn "Milvus scripts not found:"
        warn "  - $EMBED_SCRIPT"
        warn "  - $IMPORT_SCRIPT"
        warn "Please create the scripts or import manually."
        info "Expected data file: $DATA_DIR/milvus/parcels_trojmiasto_summary.csv"
    fi

    log "Milvus import complete (or skipped)!"
}

# Main execution
check_databases

case $IMPORT_TYPE in
    --all)
        import_postgis
        import_neo4j
        import_milvus
        ;;
    --postgis)
        import_postgis
        ;;
    --neo4j)
        import_neo4j
        ;;
    --milvus)
        import_milvus
        ;;
    *)
        error "Unknown import type: $IMPORT_TYPE"
        ;;
esac

log "=== Import process finished ==="
log "Run health check: curl http://localhost:8000/health"
