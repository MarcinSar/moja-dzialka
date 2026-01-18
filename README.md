# moja-dzialka

System rekomendacji dzialek budowlanych w wojewodztwie pomorskim z konwersacyjnym interfejsem AI.

## Funkcjonalnosci

- **AI Agent** - konwersacyjne wyszukiwanie dzialek w jezyku naturalnym
- **Wyszukiwanie wektorowe** - podobienstwo dzialek na podstawie cech przestrzennych (SRAI)
- **Knowledge Graph** - dane z planow miejscowych (MPZP) w Neo4j
- **Progresywne wyniki** - najpierw liczba, potem przyblizona lokalizacja, potem pelne dane
- **Monetyzacja** - 3 darmowe dzialki, potem 1 PLN/dzialka

## Architektura

```
Frontend (React + Leaflet)
    |
    v
Backend (FastAPI)
    |
    +-- PostgreSQL + PostGIS (geometrie)
    +-- Neo4j (graf MPZP)
    +-- Milvus (embeddingi)
    +-- MongoDB (leady, sesje)
    +-- Redis (cache)
```

## Wymagania

- Docker i Docker Compose
- Python 3.11+
- Node.js 20+
- Klucz API Anthropic (Claude)
- Konto Stripe (dla platnosci)

## Szybki start

### 1. Klonowanie i konfiguracja

```bash
git clone https://github.com/your-org/moja-dzialka.git
cd moja-dzialka

# Skopiuj plik konfiguracyjny
cp .env.example .env

# Uzupelnij klucze API w .env:
# - ANTHROPIC_API_KEY
# - STRIPE_SECRET_KEY
# - STRIPE_WEBHOOK_SECRET
```

### 2. Uruchomienie infrastruktury

```bash
# Uruchom wszystkie uslugi
docker compose up -d

# Sprawdz status
docker compose ps

# Logi
docker compose logs -f backend
```

### 3. Import danych

```bash
# Aktywuj srodowisko Python
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Import dzialek do PostGIS
python scripts/load_parcels.py

# Import BDOT10k
python scripts/load_bdot10k.py

# Generowanie embeddingów SRAI
python scripts/compute_embeddings.py

# Import do Milvus
python scripts/export_to_milvus.py

# Import MPZP do Neo4j
python scripts/import_mpzp_neo4j.py
```

### 4. Uruchomienie aplikacji

```bash
# Backend (jesli nie przez Docker)
cd backend
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Aplikacja dostepna pod:
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474

## Struktura projektu

```
moja-dzialka/
├── backend/                  # FastAPI backend
│   ├── app/
│   │   ├── api/             # Endpointy API
│   │   ├── services/        # Logika biznesowa
│   │   └── models/          # Modele Pydantic
│   └── scripts/             # Skrypty importu danych
├── frontend/                 # React frontend
│   └── src/
│       ├── components/      # Komponenty React
│       └── services/        # Klient API
├── scripts/
│   └── pipeline/            # Pipeline SRAI
├── docs/                    # Dokumentacja
│   ├── ARCHITECTURE.md      # Architektura systemu
│   ├── DATA_PIPELINE.md     # Pipeline danych
│   ├── GRAPH_SCHEMA.md      # Schema Neo4j
│   ├── API_SPEC.md          # Specyfikacja API
│   └── AI_AGENT.md          # Dokumentacja agenta
├── data/
│   ├── dzialki/             # Geometrie dzialek (GeoPackage)
│   ├── bdot10k/             # Dane BDOT10k (GeoPackage)
│   └── mpzp-pomorskie/      # Pokrycie MPZP
├── docker-compose.yml       # Konfiguracja Docker
├── CLAUDE.md                # Instrukcje dla Claude Code
└── README.md                # Ten plik
```

## Dostepne dane

| Zestaw | Plik | Rozmiar | Opis |
|--------|------|---------|------|
| Dzialki | `dzialki/dzialki_pomorskie.gpkg` | 449 MB | Wszystkie dzialki katastralne |
| MPZP | `mpzp-pomorskie/mpzp_pomorskie_coverage.gpkg` | 22 MB | 14,473 poligonow planow miejscowych |
| BDOT10k | `bdot10k/*.gpkg` | ~200 MB | 70+ warstw topograficznych |

Wszystkie dane w ukladzie EPSG:2180 (PUWG 1992).

## Dokumentacja

- [Architektura](docs/ARCHITECTURE.md) - szczegolowy opis komponentow
- [Pipeline danych](docs/DATA_PIPELINE.md) - SRAI, feature engineering
- [Schema grafu](docs/GRAPH_SCHEMA.md) - Neo4j, zapytania Cypher
- [Specyfikacja API](docs/API_SPEC.md) - endpointy, modele danych
- [Agent AI](docs/AI_AGENT.md) - narzedzia, przyklady konwersacji

## Zmienne srodowiskowe

```bash
# Bazy danych (ustawione w docker-compose)
POSTGRES_HOST=postgres
POSTGRES_PASSWORD=secret
NEO4J_PASSWORD=secret

# API zewnetrzne (wymagane)
ANTHROPIC_API_KEY=sk-ant-...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Aplikacja
APP_SECRET_KEY=your-secret-key
```

## Rozwoj

### Uruchomienie testow

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

### Linting

```bash
# Backend
ruff check .
mypy .

# Frontend
npm run lint
```

## Model biznesowy

| Tier | Cena | Zawartosc |
|------|------|-----------|
| FREE | 0 PLN | 3 dzialki z przyblizona lokalizacja |
| Single | 1 PLN | 1 dzialka z pelnymi danymi |
| Pack 10 | 9 PLN | 10 dzialek (10% rabat) |
| Pack 25 | 20 PLN | 25 dzialek (20% rabat) |

Metody platnosci: BLIK, karty, Przelewy24 (przez Stripe).

## Licencja

Projekt prywatny. Wszystkie prawa zastrzezone.

## Kontakt

- Email: kontakt@mojadziaka.pl
- Issues: [GitHub Issues](https://github.com/your-org/moja-dzialka/issues)
