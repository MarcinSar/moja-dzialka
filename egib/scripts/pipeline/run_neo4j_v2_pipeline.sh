#!/bin/bash
# run_neo4j_v2_pipeline.sh - Uruchomienie pełnego pipeline Neo4j v2
#
# Wykonuje wszystkie skrypty w kolejności:
# 1. 21_create_neo4j_schema_v2.py - Schemat z constraints i indexes
# 2. 22_import_category_nodes.py - Import kategorii dynamicznych (BuildingType)
# 3. 23_import_pog_zones.py - Import stref POG (7,523)
# 4. 24_import_parcels_v2.py - Import działek z nowymi relacjami
# 5. 25_create_poi_relations.py - Relacje NEAR_* z odległościami
# 6. 26_generate_parcel_embeddings.py - Embeddingi 256-dim
# 7. 27_create_adjacency_relations.py - Relacje sąsiedztwa (opcjonalnie)
#
# Użycie:
#   ./run_neo4j_v2_pipeline.sh              # wszystko
#   ./run_neo4j_v2_pipeline.sh --skip-adj   # bez sąsiedztwa (szybsze)
#   ./run_neo4j_v2_pipeline.sh --only-schema # tylko schemat
#
# Wymagania:
# - Neo4j uruchomiony na bolt://localhost:7687
# - Zmienne środowiskowe: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
# - Python 3.11+ z pakietami: neo4j, geopandas, scipy, sklearn, loguru

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
mkdir -p "$LOG_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
SKIP_ADJACENCY=false
ONLY_SCHEMA=false

for arg in "$@"; do
    case $arg in
        --skip-adj)
            SKIP_ADJACENCY=true
            shift
            ;;
        --only-schema)
            ONLY_SCHEMA=true
            shift
            ;;
    esac
done

echo "========================================"
echo " NEO4J V2 PIPELINE"
echo "========================================"
echo ""
echo "NEO4J_URI: ${NEO4J_URI:-bolt://localhost:7687}"
echo "Skip adjacency: $SKIP_ADJACENCY"
echo "Only schema: $ONLY_SCHEMA"
echo ""

run_script() {
    local script=$1
    local log_file="$LOG_DIR/$(basename $script .py)_$(date +%Y%m%d_%H%M%S).log"

    echo -e "${YELLOW}Running: $script${NC}"
    echo "  Log: $log_file"

    if python3 "$SCRIPT_DIR/$script" 2>&1 | tee "$log_file"; then
        echo -e "${GREEN}  Done!${NC}"
        return 0
    else
        echo -e "${RED}  Failed! Check log for details.${NC}"
        return 1
    fi
}

# Start time
START_TIME=$(date +%s)

echo ""
echo "=== Phase 1: Schema ==="
run_script "21_create_neo4j_schema_v2.py"

if [ "$ONLY_SCHEMA" = true ]; then
    echo ""
    echo "Only schema requested. Done."
    exit 0
fi

echo ""
echo "=== Phase 2: Category Nodes ==="
run_script "22_import_category_nodes.py"

echo ""
echo "=== Phase 3: POG Zones ==="
run_script "23_import_pog_zones.py"

echo ""
echo "=== Phase 4: Parcels ==="
run_script "24_import_parcels_v2.py"

echo ""
echo "=== Phase 5: POI Relations ==="
run_script "25_create_poi_relations.py"

echo ""
echo "=== Phase 6: Embeddings ==="
run_script "26_generate_parcel_embeddings.py"

if [ "$SKIP_ADJACENCY" = false ]; then
    echo ""
    echo "=== Phase 7: Adjacency Relations ==="
    echo "  (This may take 2-4 hours for full dataset)"
    run_script "27_create_adjacency_relations.py"
fi

# End time
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo ""
echo "========================================"
echo -e "${GREEN} PIPELINE COMPLETED${NC}"
echo "========================================"
echo "Duration: ${MINUTES}m ${SECONDS}s"
echo ""
echo "Logs: $LOG_DIR"
echo ""
echo "Next steps:"
echo "  1. Verify: python3 -c \"from neo4j import GraphDatabase; ...\""
echo "  2. Run sample queries in Neo4j Browser"
echo "  3. Test agent search"
