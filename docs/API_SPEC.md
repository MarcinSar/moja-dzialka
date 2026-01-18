# API Specification

## Overview

The moja-dzialka API provides endpoints for plot search, AI conversation, payments, and lead management.

**Base URL**: `https://api.mojadziaka.pl/v1`

**Authentication**: Session-based (cookie) for users, API key for admin endpoints

## Endpoints

### Conversation API

#### WebSocket: AI Conversation

**Endpoint**: `wss://api.mojadziaka.pl/v1/conversation/ws/{session_id}`

Connect to start or resume a conversation with the AI agent.

**URL Parameters**:
- `session_id` (string, required): Unique session identifier (UUID)

**Message Format (Client -> Server)**:
```json
{
  "type": "message",
  "content": "Szukam dzialki pod dom blisko Gdanska"
}
```

**Message Format (Server -> Client)**:
```json
{
  "type": "text",
  "content": "Dzien dobry! Chetnie pomoge znalezc..."
}
```

```json
{
  "type": "tool_call",
  "tool": "set_location_preference",
  "args": {"gmina": "Gdansk"}
}
```

```json
{
  "type": "plots",
  "plots": [
    {
      "id": "plot-123",
      "approximate_location": {"lat": 54.35, "lon": 18.64},
      "area_m2": 1050,
      "gmina": "Zukowo",
      "similarity_score": 0.94,
      "key_features": ["blisko lasu", "cicha okolica"]
    }
  ]
}
```

```json
{
  "type": "state_update",
  "credits": 3,
  "revealed_count": 0
}
```

---

### Search API

#### POST /search/count

Count plots matching criteria.

**Request**:
```json
{
  "location": {
    "gminas": ["Gdansk", "Sopot"],
    "near_point": {"lat": 54.35, "lon": 18.65},
    "radius_km": 15
  },
  "area": {
    "min_m2": 800,
    "max_m2": 1500
  },
  "mpzp": {
    "purpose": "MN",
    "require_mpzp": false
  }
}
```

**Response**:
```json
{
  "count": 127,
  "by_gmina": {
    "Zukowo": 34,
    "Kolbudy": 28,
    "Pruszcz Gdanski": 22,
    "Gdansk": 18,
    "Sopot": 8
  }
}
```

---

#### POST /search/query

Search for plots using vector similarity.

**Request**:
```json
{
  "location": {
    "gminas": ["Zukowo", "Kolbudy"],
    "radius_km": 10
  },
  "area": {
    "min_m2": 900,
    "max_m2": 1200
  },
  "mpzp": {
    "purpose": "MN"
  },
  "preferences": {
    "forest": 0.9,
    "school": 0.7,
    "quiet": 0.8,
    "shop": 0.3
  },
  "limit": 10,
  "offset": 0
}
```

**Response**:
```json
{
  "total": 87,
  "plots": [
    {
      "id": "226115_2.0003.456/7",
      "approximate_location": {
        "lat": 54.3567,
        "lon": 18.4123,
        "precision": "500m"
      },
      "area_m2": 1050,
      "gmina": "Zukowo",
      "miejscowosc": "Chwaszczyno",
      "similarity_score": 0.94,
      "key_features": [
        "300m do lasu",
        "przedszkole 1.2km",
        "cicha okolica"
      ],
      "has_mpzp": true,
      "mpzp_purpose": "MN",
      "revealed": false
    }
  ]
}
```

---

### Plots API

#### GET /plots/{id}

Get basic plot information (public data).

**Response**:
```json
{
  "id": "226115_2.0003.456/7",
  "approximate_location": {
    "lat": 54.3567,
    "lon": 18.4123
  },
  "area_m2": 1050,
  "gmina": "Zukowo",
  "miejscowosc": "Chwaszczyno",
  "has_mpzp": true,
  "mpzp_purpose": "MN",
  "key_features": [
    "blisko lasu",
    "cicha okolica"
  ]
}
```

---

#### POST /plots/{id}/reveal

Reveal full plot details (costs 1 credit).

**Request Headers**:
```
X-Session-ID: abc123-uuid
```

**Response (Success)**:
```json
{
  "success": true,
  "credits_remaining": 2,
  "plot": {
    "id": "226115_2.0003.456/7",
    "exact_location": {
      "lat": 54.35672,
      "lon": 18.41234
    },
    "nr_ewidencyjny": "456/7",
    "obreb": "0003",
    "teryt": "226115",
    "area_m2": 1047.5,
    "gmina": "Zukowo",
    "miejscowosc": "Chwaszczyno",

    "mpzp": {
      "has_mpzp": true,
      "plan_name": "MPZP Chwaszczyno Polnocne",
      "symbol": "1MN",
      "purpose": "zabudowa mieszkaniowa jednorodzinna",
      "parameters": {
        "max_wysokosc_m": 12,
        "intensywnosc": 0.4,
        "pow_biologicznie_czynna_pct": 40,
        "min_pow_dzialki_m2": 800
      },
      "restrictions": [],
      "document_url": "https://bip.zukowo.pl/..."
    },

    "distances": {
      "forest_m": 312,
      "school_m": 1245,
      "kindergarten_m": 1180,
      "shop_m": 890,
      "bus_stop_m": 420,
      "main_road_m": 1560
    },

    "neighborhood": {
      "pct_forest_500m": 0.35,
      "pct_built_500m": 0.22,
      "pct_fields_500m": 0.38,
      "road_access": "publiczna",
      "road_surface": "asfalt"
    }
  }
}
```

**Response (Insufficient Credits)**:
```json
{
  "success": false,
  "error": "insufficient_credits",
  "credits_remaining": 0,
  "message": "Brak kredytow. Kup pakiet aby zobaczyc szczegoly."
}
```

---

### Payments API

#### POST /payments/checkout

Create Stripe checkout session.

**Request**:
```json
{
  "package": "pack_10",
  "session_id": "abc123-uuid",
  "success_url": "https://mojadziaka.pl/success",
  "cancel_url": "https://mojadziaka.pl/cancel"
}
```

**Response**:
```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/...",
  "session_id": "cs_live_...",
  "expires_at": "2024-01-18T13:00:00Z"
}
```

---

#### POST /payments/webhook

Stripe webhook handler (internal).

**Request**: Stripe webhook payload

**Response**: `200 OK`

---

#### GET /payments/credits

Get current credit balance.

**Request Headers**:
```
X-Session-ID: abc123-uuid
```

**Response**:
```json
{
  "credits": 8,
  "revealed_plots": 2,
  "free_tier_used": true
}
```

---

### Leads API

#### POST /leads

Submit interest in a plot.

**Request**:
```json
{
  "plot_id": "226115_2.0003.456/7",
  "contact": {
    "name": "Jan Kowalski",
    "phone": "+48 600 123 456",
    "email": "jan@example.com"
  },
  "intent": {
    "proposed_price_pln": 250000,
    "financing": "mortgage",
    "timeline_months": 6,
    "notes": "Szukam dzialki pod budowe domu dla 4-osobowej rodziny"
  }
}
```

**Response**:
```json
{
  "lead_id": "lead_abc123",
  "message": "Dziekujemy za zgloszenie zainteresowania. Skontaktujemy sie wkrotce."
}
```

---

#### GET /leads (Admin)

List leads for management.

**Request Headers**:
```
Authorization: Bearer admin_api_key
```

**Query Parameters**:
- `status`: new, contacted, qualified, converted, rejected
- `limit`: number (default 50)
- `offset`: number (default 0)

**Response**:
```json
{
  "total": 156,
  "leads": [
    {
      "id": "lead_abc123",
      "plot_id": "226115_2.0003.456/7",
      "contact": {
        "name": "Jan Kowalski",
        "phone": "+48 600 123 456"
      },
      "intent": {
        "proposed_price_pln": 250000,
        "financing": "mortgage"
      },
      "status": "new",
      "created_at": "2024-01-18T12:00:00Z"
    }
  ]
}
```

---

#### PUT /leads/{id} (Admin)

Update lead status.

**Request**:
```json
{
  "status": "contacted",
  "notes": "Rozmowa telefoniczna - zainteresowany, umowiony na wizyte",
  "next_action": "2024-01-25",
  "assigned_to": "agent_001"
}
```

---

## Data Models

### SearchLocation

```typescript
interface SearchLocation {
  gminas?: string[];           // List of municipality names
  near_point?: {
    lat: number;
    lon: number;
  };
  radius_km?: number;          // Default: 10
}
```

### SearchArea

```typescript
interface SearchArea {
  min_m2: number;              // Required
  max_m2?: number;             // Optional upper bound
}
```

### SearchMPZP

```typescript
interface SearchMPZP {
  purpose?: "MN" | "MW" | "U" | "MN/U" | "R" | "ZL" | "any";
  require_mpzp?: boolean;      // Default: false
}
```

### SearchPreferences

```typescript
interface SearchPreferences {
  forest?: number;             // 0-1, importance of forest proximity
  school?: number;             // 0-1, importance of school proximity
  shop?: number;               // 0-1, importance of shop proximity
  public_transport?: number;   // 0-1, importance of transit
  quiet?: number;              // 0-1, importance of quiet (far from roads)
  water?: number;              // 0-1, importance of water proximity
}
```

### PlotBasic

```typescript
interface PlotBasic {
  id: string;
  approximate_location: {
    lat: number;
    lon: number;
    precision: string;         // e.g., "500m"
  };
  area_m2: number;
  gmina: string;
  miejscowosc: string;
  similarity_score: number;
  key_features: string[];
  has_mpzp: boolean;
  mpzp_purpose?: string;
  revealed: boolean;
}
```

### PlotFull

```typescript
interface PlotFull extends PlotBasic {
  exact_location: {
    lat: number;
    lon: number;
  };
  nr_ewidencyjny: string;
  obreb: string;
  teryt: string;

  mpzp?: {
    has_mpzp: boolean;
    plan_name: string;
    symbol: string;
    purpose: string;
    parameters: {
      max_wysokosc_m?: number;
      intensywnosc?: number;
      pow_biologicznie_czynna_pct?: number;
      min_pow_dzialki_m2?: number;
    };
    restrictions: string[];
    document_url?: string;
  };

  distances: {
    forest_m: number;
    school_m: number;
    kindergarten_m: number;
    shop_m: number;
    bus_stop_m: number;
    main_road_m: number;
  };

  neighborhood: {
    pct_forest_500m: number;
    pct_built_500m: number;
    pct_fields_500m: number;
    road_access: string;
    road_surface: string;
  };
}
```

### Lead

```typescript
interface Lead {
  id: string;
  plot_id: string;
  contact: {
    name: string;
    phone: string;
    email?: string;
  };
  intent: {
    proposed_price_pln?: number;
    financing?: "cash" | "mortgage" | "undecided";
    timeline_months?: number;
    notes?: string;
  };
  status: "new" | "contacted" | "qualified" | "converted" | "rejected";
  assigned_to?: string;
  created_at: string;
  updated_at: string;
  follow_ups?: {
    date: string;
    type: string;
    notes: string;
  }[];
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "error": "error_code",
  "message": "Human-readable message",
  "details": {}
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `invalid_request` | 400 | Malformed request body |
| `missing_parameter` | 400 | Required parameter missing |
| `invalid_location` | 400 | Location out of service area |
| `session_not_found` | 404 | Session ID not found |
| `plot_not_found` | 404 | Plot ID not found |
| `insufficient_credits` | 402 | Not enough credits |
| `payment_failed` | 402 | Payment processing failed |
| `rate_limited` | 429 | Too many requests |
| `internal_error` | 500 | Server error |

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/search/*` | 60/minute per IP |
| `/conversation/ws` | 1 connection per session |
| `/plots/*` | 120/minute per IP |
| `/payments/*` | 10/minute per session |
| `/leads` | 10/minute per IP |

---

## OpenAPI Specification

The full OpenAPI 3.0 specification is available at:

- Development: `http://localhost:8000/openapi.json`
- Production: `https://api.mojadziaka.pl/v1/openapi.json`

Interactive documentation (Swagger UI):
- Development: `http://localhost:8000/docs`
- Production: `https://api.mojadziaka.pl/v1/docs`
