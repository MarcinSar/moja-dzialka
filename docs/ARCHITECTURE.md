# Architecture Documentation

## System Overview

moja-dzialka is a geospatial recommendation system for finding building plots in Poland's Pomeranian Voivodeship. The system uses AI-powered conversational interface, vector similarity search, and knowledge graphs.

## High-Level Architecture

```
                                    +------------------+
                                    |   Mobile App     |
                                    | (React Native)   |
                                    +--------+---------+
                                             |
+------------------+                         |
|   Web Frontend   |                         |
|  (React+Leaflet) |                         |
+--------+---------+                         |
         |                                   |
         +----------------+------------------+
                          |
                          v
              +-----------+-----------+
              |    Load Balancer      |
              |      (nginx)          |
              +-----------+-----------+
                          |
         +----------------+----------------+
         |                                 |
         v                                 v
+--------+--------+               +--------+--------+
| FastAPI Backend |               | FastAPI Backend |
|   (Instance 1)  |               |   (Instance 2)  |
+--------+--------+               +--------+--------+
         |                                 |
         +----------------+----------------+
                          |
         +----------------+----------------+----------------+
         |                |                |                |
         v                v                v                v
+--------+----+  +--------+----+  +--------+----+  +--------+----+
|  PostgreSQL |  |    Neo4j    |  |   Milvus    |  |   MongoDB   |
|   PostGIS   |  | (Knowledge  |  |  (Vector    |  |  (Leads &   |
| (Geometries)|  |   Graph)    |  |   Search)   |  |  Sessions)  |
+-------------+  +-------------+  +-------------+  +-------------+
         |
         v
+--------+----+
|    Redis    |
|   (Cache)   |
+-------------+
```

## Component Details

### 1. Frontend Layer

#### Web Application (React + TypeScript)
- **Framework**: React 18 with TypeScript
- **Map**: Leaflet with React-Leaflet bindings
- **State**: Zustand for global state
- **Styling**: Tailwind CSS
- **Build**: Vite

Key components:
- `ChatInterface.tsx` - AI conversation UI
- `MapView.tsx` - Leaflet map with plot visualization
- `PlotCard.tsx` - Plot details display
- `PaymentModal.tsx` - Stripe checkout integration

#### Mobile Application (React Native)
- **Framework**: React Native with Expo
- **Navigation**: React Navigation
- **Maps**: react-native-maps

### 2. Backend Layer (FastAPI)

#### Core Services

```
backend/
├── app/
│   ├── main.py                 # FastAPI app initialization
│   ├── config.py               # Settings from environment
│   ├── dependencies.py         # Dependency injection
│   │
│   ├── api/
│   │   ├── conversation.py     # WebSocket chat endpoint
│   │   ├── search.py           # Plot search endpoints
│   │   ├── plots.py            # Plot CRUD operations
│   │   ├── payments.py         # Stripe integration
│   │   └── leads.py            # Lead management
│   │
│   ├── services/
│   │   ├── conversation_service.py   # AI agent orchestration
│   │   ├── search_service.py         # Vector similarity search
│   │   ├── graph_service.py          # Neo4j queries
│   │   ├── payment_service.py        # Stripe operations
│   │   └── lead_service.py           # Lead management
│   │
│   └── models/
│       ├── schemas.py          # Pydantic models
│       └── database.py         # SQLAlchemy models
│
└── scripts/
    ├── load_parcels.py         # Import parcels to PostGIS
    ├── load_bdot10k.py         # Import BDOT10k features
    ├── compute_embeddings.py   # SRAI embedding generation
    └── import_mpzp.py          # Neo4j graph import
```

#### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/conversation/ws/{session_id}` | WebSocket | AI chat interface |
| `/api/search/count` | POST | Count matching plots |
| `/api/search/query` | POST | Vector similarity search |
| `/api/plots/{id}` | GET | Get plot details |
| `/api/plots/{id}/reveal` | POST | Reveal full details (costs credit) |
| `/api/payments/checkout` | POST | Create Stripe session |
| `/api/payments/webhook` | POST | Stripe webhook handler |
| `/api/leads` | POST | Submit lead |
| `/api/leads/{id}` | GET/PUT | Manage leads |

### 3. Data Layer

#### PostgreSQL + PostGIS

**Tables:**

```sql
-- Parcels with geometries
CREATE TABLE parcels (
    id SERIAL PRIMARY KEY,
    teryt VARCHAR(20) NOT NULL,
    nr_ewidencyjny VARCHAR(50),
    obreb VARCHAR(100),
    gmina VARCHAR(100),
    powierzchnia_m2 FLOAT,
    geometry GEOMETRY(POLYGON, 2180),
    embedding_id INTEGER,
    has_mpzp BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_parcels_geometry ON parcels USING GIST(geometry);
CREATE INDEX idx_parcels_teryt ON parcels(teryt);

-- BDOT10k features (denormalized for performance)
CREATE TABLE parcel_features (
    parcel_id INTEGER REFERENCES parcels(id),
    dist_to_forest_m FLOAT,
    dist_to_school_m FLOAT,
    dist_to_shop_m FLOAT,
    dist_to_bus_stop_m FLOAT,
    dist_to_main_road_m FLOAT,
    pct_forest_500m FLOAT,
    pct_built_500m FLOAT,
    road_access_type VARCHAR(20),
    PRIMARY KEY (parcel_id)
);

-- User sessions and credits
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credits_balance INTEGER DEFAULT 3,
    revealed_plots TEXT[], -- Array of plot IDs
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Credit transactions
CREATE TABLE credit_transactions (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES user_sessions(id),
    amount INTEGER NOT NULL,
    type VARCHAR(20), -- 'purchase', 'spend'
    stripe_session_id VARCHAR(100),
    plot_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### Neo4j (Knowledge Graph)

See `docs/GRAPH_SCHEMA.md` for detailed schema.

**Key node types:**
- `Gmina` - Municipality
- `MPZP` - Local zoning plan
- `TerenMPZP` - Zoning area within plan
- `Dzialka` - Cadastral parcel
- `ParametrZabudowy` - Building parameters
- `SymbolMPZP` - Zoning designation (MN, MW, U, etc.)

#### Milvus (Vector Store)

**Collection: `parcel_embeddings`**

```python
collection_schema = {
    "fields": [
        {"name": "id", "type": DataType.INT64, "is_primary": True},
        {"name": "parcel_id", "type": DataType.VARCHAR, "max_length": 50},
        {"name": "embedding", "type": DataType.FLOAT_VECTOR, "dim": 256},
        {"name": "gmina", "type": DataType.VARCHAR, "max_length": 100},
        {"name": "area_m2", "type": DataType.FLOAT},
        {"name": "has_mpzp", "type": DataType.BOOL}
    ],
    "indexes": [
        {"field": "embedding", "type": "IVF_FLAT", "metric": "COSINE"}
    ]
}
```

#### MongoDB (Leads & Sessions)

**Collections:**
- `leads` - User interest submissions
- `conversation_sessions` - Chat history and state

See `docs/API_SPEC.md` for schema details.

#### Redis (Caching)

**Key patterns:**
- `session:{session_id}` - Conversation state (TTL: 24h)
- `search:{hash}` - Search result cache (TTL: 1h)
- `plot:{id}:features` - Plot feature cache (TTL: 24h)

### 4. External Integrations

#### Claude API (Anthropic)

Used for AI agent with tool calling.

```python
from anthropic import Anthropic

client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system=SYSTEM_PROMPT,
    tools=AGENT_TOOLS,
    messages=conversation_messages
)
```

#### Stripe

Payment processing with Polish payment methods.

```python
stripe.checkout.Session.create(
    payment_method_types=["card", "p24", "blik"],
    # ...
)
```

## Data Flow

### 1. Search Flow

```
User Query
    │
    ▼
┌─────────────────┐
│ Parse Location  │
│ & Preferences   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Build Query     │────▶│ PostGIS Filter  │
│ Embedding       │     │ (location, area)│
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│ Milvus Vector   │────▶│ Merge & Rank    │
│ Similarity      │     │ Results         │
└─────────────────┘     └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │ Return Top N    │
                        │ with Scores     │
                        └─────────────────┘
```

### 2. Conversation Flow

```
User Message
    │
    ▼
┌─────────────────┐
│ WebSocket       │
│ Handler         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Load Session    │
│ State           │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│              Claude API                  │
│  ┌───────────┐  ┌───────────────────┐  │
│  │  Tools    │  │ Conversation      │  │
│  │  Calling  │──│ Context           │  │
│  └───────────┘  └───────────────────┘  │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│ Execute Tools   │──────┐
│ (if any)        │      │
└────────┬────────┘      │
         │               │
         ▼               ▼
┌─────────────────┐  ┌─────────────────┐
│ Stream Response │  │ Update State    │
│ to Client       │  │ (credits, etc.) │
└─────────────────┘  └─────────────────┘
```

## Deployment

### Docker Compose (Development)

See `docker-compose.yml` in project root.

### Production Architecture

```
                    +------------------+
                    |   Cloudflare     |
                    |   (CDN + WAF)    |
                    +--------+---------+
                             |
                    +--------+---------+
                    |   nginx          |
                    |   (reverse proxy)|
                    +--------+---------+
                             |
         +-------------------+-------------------+
         |                   |                   |
+--------+--------+  +-------+--------+  +-------+--------+
|  Docker Swarm   |  |  Docker Swarm  |  |  Docker Swarm  |
|  Node 1         |  |  Node 2        |  |  Node 3        |
|  - Backend x2   |  |  - Backend x2  |  |  - Backend x2  |
|  - Frontend     |  |  - Frontend    |  |  - Frontend    |
+-----------------+  +----------------+  +----------------+
         |                   |                   |
         +-------------------+-------------------+
                             |
              +--------------+--------------+
              |              |              |
    +---------+----+ +-------+------+ +-----+--------+
    | PostgreSQL   | |    Neo4j     | |   Milvus     |
    | (Primary)    | |   (Single)   | |  (Cluster)   |
    +--------------+ +--------------+ +--------------+
              |
    +---------+----+
    | PostgreSQL   |
    | (Replica)    |
    +--------------+
```

### Environment Variables

```bash
# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=moja_dzialka
POSTGRES_USER=app
POSTGRES_PASSWORD=secret

# Neo4j
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=secret

# Milvus
MILVUS_HOST=milvus
MILVUS_PORT=19530

# MongoDB
MONGODB_URI=mongodb://mongo:27017/moja_dzialka

# Redis
REDIS_URL=redis://redis:6379

# External APIs
ANTHROPIC_API_KEY=sk-ant-...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# App
APP_SECRET_KEY=...
CORS_ORIGINS=["https://mojadziaka.pl"]
```

## Security Considerations

1. **API Authentication**: Session-based for users, API keys for admin
2. **Rate Limiting**: 100 requests/minute per IP
3. **Input Validation**: Pydantic models for all inputs
4. **SQL Injection**: SQLAlchemy ORM with parameterized queries
5. **XSS Prevention**: React's built-in escaping, CSP headers
6. **HTTPS**: Enforced via Cloudflare

## Monitoring

- **Logs**: Structured JSON logs to stdout, collected by Docker
- **Metrics**: Prometheus + Grafana
- **Tracing**: OpenTelemetry (optional)
- **Alerts**: PagerDuty/Slack integration

## Scaling Considerations

1. **Read replicas** for PostgreSQL under heavy load
2. **Milvus cluster** for vector search scaling
3. **Redis cluster** for session scaling
4. **CDN caching** for static assets and API responses
