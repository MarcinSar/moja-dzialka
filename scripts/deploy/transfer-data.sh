#!/bin/bash
# =============================================================================
# transfer-data.sh - Pakowanie i transfer danych na serwer
# =============================================================================
#
# Użycie:
#   ./scripts/deploy/transfer-data.sh pack          # Spakuj dane lokalnie
#   ./scripts/deploy/transfer-data.sh send SERVER   # Wyślij na serwer
#   ./scripts/deploy/transfer-data.sh all SERVER    # Spakuj i wyślij
#
# Przykład:
#   ./scripts/deploy/transfer-data.sh all user@77.42.86.222
#
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ARCHIVE_NAME="moja-dzialka-data.tar.gz"
ARCHIVE_PATH="$PROJECT_ROOT/$ARCHIVE_NAME"

# Kolory
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

pack_data() {
    log_info "Pakowanie danych..."
    cd "$PROJECT_ROOT"

    # Lista plików do spakowania
    FILES_TO_PACK=(
        "data/ready-for-import/neo4j/*.csv"
        "data/ready-for-import/postgis/*.gpkg"
        "egib/data/processed/parcels_enriched.gpkg"
        "egib/data/processed/water_classified.gpkg"
        "egib/data/processed/pog_trojmiasto.gpkg"
        "egib/data/processed/poi_trojmiasto.gpkg"
    )

    # Sprawdź co istnieje
    EXISTING_FILES=""
    for pattern in "${FILES_TO_PACK[@]}"; do
        for f in $pattern; do
            if [ -f "$f" ]; then
                EXISTING_FILES="$EXISTING_FILES $f"
            fi
        done
    done

    if [ -z "$EXISTING_FILES" ]; then
        log_error "Nie znaleziono plików do spakowania!"
        exit 1
    fi

    # Pakuj
    log_info "Tworzenie archiwum: $ARCHIVE_NAME"
    tar -czvf "$ARCHIVE_NAME" $EXISTING_FILES

    # Pokaż rozmiar
    SIZE=$(du -h "$ARCHIVE_NAME" | cut -f1)
    log_info "Archiwum utworzone: $SIZE"
    log_info "Lokalizacja: $ARCHIVE_PATH"
}

send_data() {
    SERVER="$1"

    if [ -z "$SERVER" ]; then
        log_error "Podaj adres serwera: ./transfer-data.sh send user@server"
        exit 1
    fi

    if [ ! -f "$ARCHIVE_PATH" ]; then
        log_error "Archiwum nie istnieje. Najpierw uruchom: ./transfer-data.sh pack"
        exit 1
    fi

    log_info "Wysyłanie na serwer: $SERVER"

    # Wyślij archiwum
    rsync -avz --progress "$ARCHIVE_PATH" "$SERVER:~/"

    log_info "Transfer zakończony!"
    log_info ""
    log_info "Na serwerze wykonaj:"
    log_info "  cd ~/moja-dzialka"
    log_info "  tar -xzvf ~/$ARCHIVE_NAME"
    log_info "  docker compose up -d"
    log_info "  # Import Neo4j:"
    log_info "  NEO4J_PASSWORD=secretpassword python egib/scripts/pipeline/15_create_neo4j_schema.py"
    log_info "  NEO4J_PASSWORD=secretpassword python egib/scripts/pipeline/16_import_neo4j_full.py"
    log_info "  NEO4J_PASSWORD=secretpassword python egib/scripts/pipeline/17_create_spatial_relations.py"
}

show_help() {
    echo "Użycie: $0 {pack|send|all} [SERVER]"
    echo ""
    echo "Komendy:"
    echo "  pack         Spakuj dane do archiwum"
    echo "  send SERVER  Wyślij archiwum na serwer"
    echo "  all SERVER   Spakuj i wyślij"
    echo ""
    echo "Przykład:"
    echo "  $0 all marcin@77.42.86.222"
}

# Main
case "$1" in
    pack)
        pack_data
        ;;
    send)
        send_data "$2"
        ;;
    all)
        pack_data
        send_data "$2"
        ;;
    *)
        show_help
        exit 1
        ;;
esac
