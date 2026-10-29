# Urja Meter Ops — API Wrapper

A clean REST API service built over the internal **Urja Meter Ops** portal (`https://urja-ops.flockenergy.tech`).

The portal is used by utility field and operations staff to inspect smart-meter details, grid network hierarchy, and consumption readings. It lacks an official public API, so this service reverse-engineers the portal's internal endpoints, normalizes the data, and exposes a structured REST API for programmatic access.

---

## Deliverables & Core Files

- **API Source Code**: Located in `app/` (FastAPI + httpx + Pydantic).
- **Portal Protocol Write-up**: [`PROTOCOL.md`](./PROTOCOL.md) — How the portal works under the hood (auth, session cookies, endpoints, and the HMAC signature scheme).
- **OpenAPI Specification**: [`openapi.json`](./openapi.json) — OpenAPI 3.1 specification.
- **Interactive Documentation**: Served live at `http://localhost:8000/docs` (Scalar UI) and `http://localhost:8000/openapi.json`.
- **Reflection**: [`REFLECTION.md`](./REFLECTION.md) — Answers to the 5 take-home reflection questions.

---

## System Architecture

```text
Downstream Clients / Programs
              │
              ▼
   ┌───────────────────────────────────────────────┐
   │             FastAPI API Service               │
   │                                               │
   │  • /meters (search, filter, pagination)       │
   │  • /meters/{id} (nameplate, location, tree)   │
   │  • /meters/{id}/readings (interval readings)  │
   │  • /transformers (distribution transformers)  │
   │  • /network (full 7-level distribution tree)  │
   │                                               │
   │  [In-memory TTL Cache]  [HMAC Request Signer] │
   │           │                     │             │
   │           └──────────┬──────────┘             │
   │                      ▼                        │
   │             Portal HTTP Client                │
   │     (Persistent session + auto re-auth)       │
   └──────────────────────┬────────────────────────┘
                          │
                          ▼ (HTTPS + Cookie + HMAC)
             Urja Meter Ops Web Portal
         https://urja-ops.flockenergy.tech
```

### Key Technical Decisions:
1. **Bulk dataset extraction via HMAC-SHA256 signing**: Instead of scraping 403 individual pages, I reverse-engineered the portal's "Export all meters" feature from the SvelteKit JS bundle. It fetches the signing key from `/portal/keys` and signs `/portal/export?page=1` using HMAC-SHA256. This fetches all 403 meters with their full 7-level hierarchy and GPS coordinates in a single call.
2. **Local query & filtering layer**: The portal's web interface only has a basic text search. This API adds faceted filtering (`make`, `phase_type`, `install_status`, `dt_code`) in addition to text search across meter IDs and serial numbers.
3. **Data normalization**: Upstream uses inconsistent data types (voltages and energy counters formatted as strings, and dates formatted as Indian strings like `23/06/2026 23:30`). The API normalizes all numbers to floats/ints and all timestamps to standard ISO-8601 UTC datetimes.
4. **Resilient session management**: A single shared HTTP client keeps the session token. If the session expires during a long-running instance, an `asyncio.Lock` ensures only one re-auth happens (preventing thundering herd problems) and retries the failed request once.
5. **Polite concurrency**: Legacy utility systems are easily overwhelmed. An `asyncio.Semaphore(3)` limits concurrent outgoing requests to the portal.

---

## Quickstart

### 1. Requirements
- Python 3.10+
- pip

### 2. Setup

```bash
# Clone the repository
git clone <repo-url> urja-api
cd urja-api

# Create and activate virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

The app loads settings from `.env`. The provided credentials and portal URL are preset in `.env.example`:

```bash
# On Linux/macOS:
cp .env.example .env
# On Windows (PowerShell):
Copy-Item .env.example .env
```

Default configuration:
```env
PORTAL_URL=https://urja-ops.flockenergy.tech
PORTAL_EMAIL=operator@urja.local
PORTAL_PASSWORD=urja-ops-2026

CACHE_TTL_METERS=300
CACHE_TTL_READINGS=60
CACHE_TTL_TRANSFORMERS=300
PORTAL_TIMEOUT=30
PORTAL_MAX_CONCURRENCY=3
```

### 4. Run the Service

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The service logs in to the portal at startup and serves requests at:
- **Interactive API Documentation**: `http://localhost:8000/docs`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

### 5. Run the Test Suite

A standalone test suite is included in `test_api.py` that verifies all endpoints against the live portal:

```bash
python test_api.py
```

---

## Sample Requests

### 1. List meters with filters
Filter for single-phase meters made by `Genus`:
```bash
curl -s "http://localhost:8000/meters?make=Genus&phase_type=single&page=1&page_size=2"
```

Response:
```json
{
  "data": [
    {
      "meter_id": "J100003",
      "serial_no": "L&84997",
      "make": "Genus",
      "phase_type": "single",
      "install_status": "Installed",
      "dt_code": "DT-004",
      "install_type": "Whole Current",
      "build": "legacy",
      "location": {
        "latitude": 26.8912,
        "longitude": 75.8271
      },
      "hierarchy": {
        "zone": { "name": "Jaipur Zone 1", "code": "Z-01" },
        "circle": { "name": "Circle 1", "code": "C-01" },
        "division": { "name": "Division 1", "code": "D-01" },
        "subdivision": { "name": "Subdivision 1", "code": "SD-01" },
        "substation": { "name": "Substation 1", "code": "SS-01" },
        "feeder": { "name": "Feeder 1", "code": "F-001" },
        "dt": { "name": "Raja Park DT 4", "code": "DT-004" }
      }
    }
  ],
  "total": 52,
  "page": 1,
  "page_size": 2,
  "total_pages": 26
}
```

### 2. Get single meter details
```bash
curl -s http://localhost:8000/meters/J100000
```

### 3. Get 30-minute consumption readings
```bash
curl -s http://localhost:8000/meters/J100000/readings
```

Response:
```json
{
  "meter_id": "J100000",
  "count": 337,
  "readings": [
    {
      "timestamp": "2026-06-23T23:30:00",
      "kwh": 48438.74,
      "kvah": 52313.84,
      "voltage_r": 226.0
    },
    {
      "timestamp": "2026-06-24T00:00:00",
      "kwh": 48439.16,
      "kvah": 52314.29,
      "voltage_r": 229.0
    }
  ]
}
```

### 4. Get full 7-level network tree
```bash
curl -s http://localhost:8000/network
```

Response:
```json
{
  "id": "ROOT",
  "name": "Distribution Network",
  "level": "root",
  "meter_count": 403,
  "children": [
    {
      "id": "Z-01",
      "name": "Jaipur Zone 1",
      "level": "zone",
      "meter_count": 143,
      "children": [...]
    }
  ]
}
```

---

## Assumptions & Trade-offs

- **Read-only**: The assignment states the portal should be treated as read-only. No mutation routes are implemented.
- **In-memory cache**: With 403 meters and 40 transformers, the entire dataset is under 1 MB. An in-memory TTL cache (`cachetools`) avoids adding Redis or Postgres dependencies for a local take-home evaluation.
- **Scale limits**: In-memory filtering works up to ~50,000 meters. For a production utility with millions of meters, I would index data into SQLite or PostgreSQL with a background ingestion worker.
- **Freshness**: Network topology changes rarely, so it is cached for 5 minutes. Consumption readings update periodically (30-minute intervals), so they are cached for 1 minute.
- **What was intentionally skipped**:
  - *Custom web UI*: I deliberately focused the 4-6 hour budget on the core service (reverse-engineering the portal, data models, resilient auth, and clean API design) rather than building a frontend.
  - *API key auth on our wrapper*: Kept open for reviewer convenience. In production, this would sit behind an API gateway with token validation.
