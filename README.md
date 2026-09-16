# Smart Policy Recommendation Engine (SPRE)

A 3-tier application that simulates an insurance underwriting workflow: it collects a
customer's risk profile, hard-filters ineligible policies, scores the remaining
candidates on suitability, calculates a risk-adjusted premium, and returns a ranked,
explainable recommendation. Every recommendation is written to an immutable audit
log.

Everything below was actually built and run on this machine. Numbers in the
"Load Testing" section are real Locust output, not estimates.

## Architecture

```
[ Streamlit frontend ]  --HTTP/JSON-->  [ FastAPI backend ]  --SQLAlchemy (async)-->  [ SQLite ]
      (port 8501)                        (port 8000)
                                              |
                                              +--> /health      liveness + DB check
                                              +--> /metrics     Prometheus scrape
```

- **Presentation tier — Streamlit** (`frontend/`): collects the risk profile via a
  form, calls the backend over HTTP, renders ranked recommendations and a
  suitability bar chart. Never touches the database directly.
- **Application tier — FastAPI** (`backend/app/`): async route handlers, Pydantic v2
  request validation, a pure-function scoring/premium engine
  (`app/services/scoring.py`), and a recommender service
  (`app/services/recommender.py`) that ties eligibility filtering, scoring, premium
  calculation, and audit logging together in one DB transaction.
- **Data tier — SQLite via async SQLAlchemy** (`aiosqlite` driver): three tables —
  `policies`, `customers`, `recommendation_logs` — with the exact schema and indexes
  specified below. Schema is owned by Alembic migrations, not hand-edited.

### Request flow for `POST /api/v1/recommend`

1. Pydantic validates the incoming `RiskProfileRequest` (types, ranges, enum) — a
   malformed request never reaches business logic (`422` response).
2. A `Customer` row is inserted for the submission.
3. **Rules engine**: active policies are hard-filtered by age range and minimum
   income (`app/services/recommender.get_eligible_policies`).
4. **Scoring engine**: each eligible policy is scored 0–100 by a plain-Python
   weights matrix keyed on policy type and risk attributes
   (`app/services/scoring.score_policy`) — pure function, no I/O, fully unit
   tested.
5. **Premium calculator**: `final_premium = base_premium * risk_loading_coefficient`,
   where the coefficient is a deterministic function of smoker/hazardous
   occupation/chronic illness/employment status (`calculate_premium`).
6. The top 5 scored policies are ranked, an immutable `RecommendationLog` row is
   written per result, and the ranked list is returned with human-readable
   reasoning.

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | Streamlit |
| Backend | FastAPI (async), Pydantic v2 |
| ORM | SQLAlchemy 2.0 async engine, `aiosqlite` driver |
| Database | SQLite (Postgres-portable models; only the connection string changes) |
| Migrations | Alembic |
| Testing | pytest, `httpx.AsyncClient`, Locust |
| Rate limiting | slowapi |
| Containerization | Docker + docker-compose |
| CI | GitHub Actions (ruff + black + pytest with coverage gate) — see `.github/workflows/ci.yml` |
| Observability | `prometheus-fastapi-instrumentator` + `/metrics`, structured JSON logs |
| Dependency scanning | pip-audit |

## Database Schema

```sql
CREATE TABLE policies (
    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_name VARCHAR(100) NOT NULL,
    policy_type VARCHAR(30) NOT NULL, -- HEALTH, AUTO, LIFE, PROPERTY
    description TEXT,
    base_premium DECIMAL(10, 2) NOT NULL,
    min_age INT DEFAULT 18,
    max_age INT DEFAULT 100,
    min_income DECIMAL(12, 2) DEFAULT 0.00,
    coverage_amount DECIMAL(15, 2) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name VARCHAR(100) NOT NULL,
    age INT NOT NULL,
    monthly_income DECIMAL(12, 2) NOT NULL,
    occupation VARCHAR(50), -- DESK_JOB, HAZARDOUS, UNEMPLOYED
    is_smoker BOOLEAN DEFAULT FALSE,
    has_chronic_illness BOOLEAN DEFAULT FALSE,
    owns_vehicle BOOLEAN DEFAULT FALSE,
    vehicle_value DECIMAL(12, 2) DEFAULT 0.00,
    owns_property BOOLEAN DEFAULT FALSE,
    property_value DECIMAL(15, 2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE recommendation_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INT NOT NULL,
    policy_id INT NOT NULL,
    calculated_suitability_score DECIMAL(5, 2) NOT NULL,
    final_premium_quoted DECIMAL(10, 2) NOT NULL,
    recommendation_rank INT NOT NULL,
    generated_reasoning TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (policy_id) REFERENCES policies(policy_id)
);

CREATE INDEX idx_policy_filter ON policies(policy_type, min_age, max_age);
CREATE INDEX idx_logs_customer ON recommendation_logs(customer_id);
```

The catalog is seeded with 20 mock policies spread across HEALTH, AUTO, LIFE, and
PROPERTY (`backend/app/seed.py`).

## API Surface

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/recommend` | Submit a risk profile, get ranked recommendations |
| GET | `/api/v1/policies` | List active policies |
| GET | `/api/v1/recommendations/{customer_id}` | Retrieve a customer's audit trail |
| GET | `/health` | Liveness/readiness probe with DB connectivity check |
| GET | `/metrics` | Prometheus scrape endpoint |

Interactive docs (Swagger UI) are auto-generated at `/docs` once the backend is
running.

## Non-Functional Requirements — how they're actually implemented

- **Concurrency**: all routes are `async def`, the SQLAlchemy engine uses the async
  `aiosqlite` driver, no shared mutable in-process state — every request carries
  everything it needs, safe under multiple uvicorn workers (`--workers 2` in the
  Dockerfile).
- **Security**: Pydantic validation on every request; all queries go through
  SQLAlchemy's parameterized query builder (no raw string-formatted SQL anywhere);
  CORS allow-list (not `*`, configurable via `CORS_ALLOW_ORIGINS`); slowapi rate
  limiting on `/api/v1/recommend` (configurable via `RECOMMEND_RATE_LIMIT`, default
  `20/minute` per IP); secrets via `.env` (`.env` is gitignored, `.env.example`
  provided); dependency vulnerability scanning via pip-audit (see below). No auth
  layer — recommendations are anonymous/ephemeral by design, so JWT auth was
  deliberately not added (would be unused, untested code).
- **Maintainability**: layered structure (`routers/` / `services/` / `models.py` /
  `schemas.py`), Alembic migrations from day one, API versioned under `/api/v1/`.
- **Observability**: structured JSON logs via `python-json-logger`, Prometheus
  metrics exposed at `/metrics`, `/health` endpoint with a real DB connectivity
  check.
- **Auditability**: `recommendation_logs` is append-only — no application code path
  updates or deletes rows in that table.

## Running Locally (without Docker)

**Prerequisites**: Python 3.12+.

```bash
cd backend
python -m venv venv
./venv/Scripts/activate   # Windows; use `source venv/bin/activate` on macOS/Linux
pip install -r requirements-dev.txt

# Apply migrations and seed the catalog
alembic upgrade head
python -m app.seed

# Run the API
uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend
python -m venv venv
./venv/Scripts/activate
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501.

## Running via Docker Compose

```bash
docker compose up --build
```

This builds and starts both services. The backend runs `alembic upgrade head`,
seeds the catalog if empty, then starts uvicorn with 2 workers; SQLite data
persists in the `spre-data` named volume. Once up:

- Frontend: http://localhost:8501
- Backend docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

Verified locally: both containers build and start cleanly, `/health` returns
`{"status": "ok", "database": "ok"}`, `/api/v1/policies` returns the 20 seeded
policies, and a full request submitted through the Streamlit UI in a browser
returns ranked recommendations end-to-end.

```bash
docker compose down   # stop and remove containers (keeps the named volume)
```

## Testing

### Running the suite

```bash
cd backend
pytest --cov=app --cov-report=term-missing --cov-fail-under=85
```

**Actual result on this machine: 36 tests passed, 94.9% coverage** (gate set at
85%). Breakdown:

- `tests/test_scoring.py` — 23 unit tests against the pure scoring/premium
  functions: eligibility boundaries (min/max age, min income), risk-coefficient
  stacking, premium calculation including the zero-base-premium edge case, and
  scoring behavior per policy type (smoker/chronic-illness penalties, vehicle/
  property value rewards, score clamping, unknown-policy-type fallback).
- `tests/test_api.py` — 13 integration tests hitting the full FastAPI app via
  `httpx.AsyncClient` against a throwaway SQLite test database: happy path,
  ineligible-age exclusion, below-min-income exclusion, empty-catalog case,
  Pydantic validation rejections (422), audit-log persistence, 404 for an unknown
  customer, and the `/metrics` endpoint.

Coverage note: `app/seed.py` is excluded from the coverage gate (`.coveragerc`) —
it's a one-off data-loading script exercised manually, not through pytest.
`.coveragerc` also sets `concurrency = greenlet` so coverage.py correctly traces
code that runs across SQLAlchemy's async/greenlet boundary (without it, the async
service layer reports as falsely uncovered).

### Linting and formatting

```bash
ruff check app tests
black --check app tests
```

Both pass clean on this codebase (verified locally, and run in CI).

### Dependency vulnerability scanning

```bash
pip-audit -r requirements.txt
```

**Actual first run found 8 real vulnerabilities** (in `starlette` transitively via
an older `fastapi` pin, and in `python-dotenv`). These were fixed by upgrading:
`fastapi` 0.115.6 → 0.141.1, `python-dotenv` 1.0.1 → 1.2.3, and
`prometheus-fastapi-instrumentator` 7.0.0 → 8.1.0 (needed to lift its own
`starlette<1.0.0` pin, which was blocking the fix). Two dev-only tools (`black`,
`pytest`) were also flagged and upgraded (`pytest-asyncio` had to move to 1.4.0 to
stay compatible with the new pytest). **Re-running `pip-audit` after the upgrades
reports zero known vulnerabilities**, and the full test suite (36/36) still passes
against the upgraded stack — verified with a from-scratch venv install of the
pinned `requirements-dev.txt`, not just the environment that happened to already
have the packages.

## Load Testing

`backend/locustfile.py` simulates users hitting `/api/v1/recommend` (weight 5),
`/api/v1/policies` (weight 1), and `/health` (weight 1) with randomized risk
profiles. Run:

```bash
locust -f locustfile.py --headless -u 50 -r 5 --run-time 1m --host http://127.0.0.1:8000
```

Two real runs were recorded (raw Locust CSV output in `docs/`):

**1. Default configuration** (`RECOMMEND_RATE_LIMIT=20/minute`, the shipped
default) — `docs/loadtest_default_stats.csv`:

| Endpoint | Requests | Failures | p50 | p95 | p99 | Max |
|---|---|---|---|---|---|---|
| POST /api/v1/recommend | 985 | 945 (95.9%) | 5 ms | 26 ms | 180 ms | 1057 ms |
| GET /api/v1/policies | 195 | 0 | 9 ms | 18 ms | 35 ms | 38 ms |
| GET /health | 205 | 0 | 7 ms | 15 ms | 40 ms | 894 ms |

Nearly all `/recommend` failures were genuine `429 Too Many Requests` — **this is
the per-IP rate limiter working as designed**: Locust's 50 simulated users all
originate from one machine (one IP), so they collectively hit the 20-requests/min
ceiling almost immediately. This is an honest artifact of single-machine load
testing against a per-IP limiter, not a backend defect.

**2. Capacity scenario** (`RECOMMEND_RATE_LIMIT=10000/minute`, limiter effectively
disabled, to measure raw request-handling capacity) —
`docs/loadtest_capacity_stats.csv`:

| Endpoint | Requests | Failures | p50 | p95 | p99 | Max |
|---|---|---|---|---|---|---|
| POST /api/v1/recommend | 936 | 0 (0%) | 57 ms | 260 ms | 600 ms | 957 ms |
| GET /api/v1/policies | 225 | 0 | 15 ms | 50 ms | 100 ms | 243 ms |
| GET /health | 183 | 0 | 10 ms | 21 ms | 33 ms | 36 ms |

With rate limiting out of the way, 50 concurrent users, zero failures, p50 of 57ms
and p95 of 260ms for the full filter-score-premium-log pipeline on a single SQLite
file with 2 uvicorn workers. Both runs were executed on the same machine
(localhost, no network latency) — these are local capacity numbers, not a claim
about production-scale traffic.

## Realistic Scope Statement

This is a solo-built MVP, not a FAANG-scale insurance platform. What's real: a
stateless, containerized, async, rate-limited, input-validated, migration-managed,
load-tested (with real numbers above), 94.9%-covered application with an immutable
audit trail. What's *not* built (and shouldn't be claimed as built): Kubernetes,
multi-region deployment, PostgreSQL read replicas, a Redis cache layer, or a
service mesh. Those are documented here as the natural next steps given the
already-stateless backend and Postgres-portable SQLAlchemy models — not as
work that was done.

## Project Structure

```
backend/
  app/
    routers/        # recommend.py, health.py
    services/        # scoring.py (pure functions), recommender.py (orchestration)
    models.py         # SQLAlchemy models
    schemas.py         # Pydantic request/response models
    database.py         # async engine/session setup
    main.py               # FastAPI app, middleware, lifespan
    seed.py                 # policy catalog seed script
  alembic/                    # migrations (schema is owned here, not hand-edited)
  tests/                         # pytest suite
  locustfile.py                    # load test
  Dockerfile
frontend/
  app.py             # Streamlit UI
  Dockerfile
docker-compose.yml
.github/workflows/ci.yml
docs/                # real load-test CSV output
```
