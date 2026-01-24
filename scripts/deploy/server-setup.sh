#!/bin/bash
# =============================================================================
# server-setup.sh - Konfiguracja serwera i import danych
# =============================================================================
#
# Uruchom na serwerze po transferze danych:
#   cd ~/moja-dzialka
#   ./scripts/deploy/server-setup.sh
#
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Kolory
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

cd "$PROJECT_ROOT"

# =============================================================================
# 1. Sprawdź wymagania
# =============================================================================
log_step "1/6 Sprawdzanie wymagań..."

if ! command -v docker &> /dev/null; then
    log_error "Docker nie jest zainstalowany!"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    log_error "Python3 nie jest zainstalowany!"
    exit 1
fi

# =============================================================================
# 2. Rozpakuj dane (jeśli archiwum istnieje)
# =============================================================================
log_step "2/6 Rozpakowywanie danych..."

ARCHIVE="$HOME/moja-dzialka-data.tar.gz"
if [ -f "$ARCHIVE" ]; then
    log_info "Rozpakowywanie $ARCHIVE..."
    tar -xzvf "$ARCHIVE"
    log_info "Dane rozpakowane"
else
    log_warn "Archiwum nie znalezione: $ARCHIVE"
    log_warn "Upewnij się, że dane są w data/ready-for-import/"
fi

# =============================================================================
# 3. Utwórz .env jeśli nie istnieje
# =============================================================================
log_step "3/6 Konfiguracja środowiska..."

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        log_warn "Utworzono .env z .env.example"
        log_warn "WAŻNE: Ustaw ANTHROPIC_API_KEY w .env!"
    else
        log_error "Brak .env.example!"
        exit 1
    fi
else
    log_info ".env już istnieje"
fi

# Sprawdź czy ANTHROPIC_API_KEY jest ustawiony
if grep -q "ANTHROPIC_API_KEY=sk-ant-api03-..." .env 2>/dev/null; then
    log_warn "ANTHROPIC_API_KEY nie jest skonfigurowany w .env!"
fi

# =============================================================================
# 4. Uruchom Docker Compose
# =============================================================================
log_step "4/6 Uruchamianie kontenerów Docker..."

docker compose pull
docker compose up -d

log_info "Czekanie na uruchomienie baz danych..."
sleep 30

# Sprawdź health
docker compose ps

# =============================================================================
# 5. Import danych do Neo4j
# =============================================================================
log_step "5/6 Import danych do Neo4j..."

# Pobierz hasło Neo4j z .env lub użyj domyślnego
NEO4J_PASSWORD=$(grep NEO4J_PASSWORD .env 2>/dev/null | cut -d= -f2 || echo "secretpassword")
export NEO4J_PASSWORD

# Zainstaluj wymagania Python jeśli potrzeba
if ! python3 -c "import neo4j" 2>/dev/null; then
    log_info "Instalowanie neo4j Python driver..."
    pip3 install neo4j loguru pandas geopandas
fi

# Uruchom skrypty importu
log_info "Tworzenie schematu Neo4j..."
python3 egib/scripts/pipeline/15_create_neo4j_schema.py

log_info "Import danych do Neo4j..."
python3 egib/scripts/pipeline/16_import_neo4j_full.py

log_info "Tworzenie relacji przestrzennych..."
python3 egib/scripts/pipeline/17_create_spatial_relations.py

# =============================================================================
# 6. Weryfikacja
# =============================================================================
log_step "6/6 Weryfikacja..."

echo ""
log_info "=== Status kontenerów ==="
docker compose ps

echo ""
log_info "=== Test API ==="
curl -s http://localhost:8000/health | python3 -m json.tool || log_warn "Backend jeszcze nie gotowy"

echo ""
log_info "=== Test Neo4j ==="
python3 -c "
from neo4j import GraphDatabase
import os
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', os.environ.get('NEO4J_PASSWORD', 'secretpassword')))
with driver.session() as s:
    r = s.run('MATCH (p:Parcel) RETURN count(p) as c').single()
    print(f'Działki w Neo4j: {r[\"c\"]:,}')
driver.close()
"

echo ""
log_info "=========================================="
log_info "Setup zakończony!"
log_info "=========================================="
log_info ""
log_info "Dostęp:"
log_info "  Frontend: http://localhost:3000"
log_info "  Backend:  http://localhost:8000"
log_info "  Neo4j:    http://localhost:7474"
log_info ""
log_info "Następne kroki:"
log_info "  1. Skonfiguruj ANTHROPIC_API_KEY w .env"
log_info "  2. Uruchom ponownie: docker compose restart backend"
log_info "  3. Skonfiguruj Nginx i SSL (patrz docs/DEPLOYMENT.md)"
