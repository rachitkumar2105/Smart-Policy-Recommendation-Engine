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
[ React + TS SPA ]  --HTTP/JSON-->  [ FastAPI backend ]  --SQLAlchemy (async)-->  [ SQLite ]
   (port 5173)                       (port 8000)               |
                                          |                     +--> ml/model.joblib (GradientBoostingRegressor)
                                          +--> /health      liveness + DB check
                                          +--> /metrics     Prometheus scrape
```

- **Presentation tier — React + TypeScript (Vite SPA)** (`frontend/`): a risk-profile
  form with client-side validation mirroring the backend's Pydantic constraints,
  and a results view rendering ranked recommendations, the rule-based/ML premium
  breakdown, and a hand-rolled SVG suitability chart. Calls the backend over REST;
  never touches the database directly. Replaces the original Streamlit MVP.
- **Application tier — FastAPI** (`backend/app/`): async route handlers, Pydantic v2
  request validation, a pure-function scoring/premium engine
  (`app/services/scoring.py`), a trained ML inference layer (`backend/ml/`), and a
  recommender service (`app/services/recommender.py`) that ties eligibility
  filtering, scoring, hybrid premium calculation, and audit logging together in one
  DB transaction.
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
5. **ML signal**: the profile's `age/sex/bmi/children/smoker/region` are run through
   a trained regression model (`backend/ml/inference.py`) that predicts annual
   medical charges, converted into a bounded premium-loading adjustment.
6. **Hybrid premium calculator**: `final_premium = base_premium * (1 + rule_based_adjustment + ml_predicted_adjustment)`
   (`calculate_hybrid_premium`) — both components are deterministic given the same
   inputs and are returned separately in the API response, so the result stays
   explainable rather than becoming a black box.
7. The top 5 scored policies are ranked, an immutable `RecommendationLog` row is
   written per result, and the ranked list is returned with human-readable
   reasoning plus both adjustment components.

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | React + TypeScript (Vite SPA) |
| Backend | FastAPI (async), Pydantic v2 |
| ML | scikit-learn (Gradient Boosting Regressor), pandas, joblib |
| ORM | SQLAlchemy 2.0 async engine, `aiosqlite` driver |
| Database | SQLite (Postgres-portable models; only the connection string changes) |
| Migrations | Alembic |
| Testing | pytest, `httpx.AsyncClient`, Locust, Vitest + React Testing Library |
| Rate limiting | slowapi |
| Containerization | Docker + docker-compose |
| CI | GitHub Actions — backend job (ruff + black + pytest with coverage gate + pip-audit) and frontend job (lint + vitest + build) — see `.github/workflows/ci.yml` |
| Observability | `prometheus-fastapi-instrumentator` + `/metrics`, structured JSON logs, Prometheus + Grafana |
| Dependency scanning | pip-audit (backend), npm audit (frontend) |

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
running. `RiskProfileRequest` gained four new optional fields for the ML signal
(`sex`, `bmi`, `children`, `region` — all default so the contract stays backward
compatible), and each `RecommendationItem` now also reports
`rule_based_adjustment`, `ml_predicted_adjustment`, and `ml_predicted_charges`
alongside `final_premium`.

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
  check, plus a Prometheus + Grafana stack (`monitoring/`) with a pre-provisioned
  dashboard (request rate by endpoint, error rate, p50/p95/p99 latency, total
  requests, backend-up status) — datasource and dashboard both auto-provisioned
  on startup, no manual clicking required.
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
npm install
npm run dev
```

Open http://localhost:5173.

## Machine Learning Component

`backend/ml/` adds a genuine, evaluated ML signal alongside the deterministic
rule-based engine — it augments the premium calculation, it does not replace it.

**Dataset**: the public "Medical Cost Personal Datasets" (`insurance.csv`, 1,338 real
rows: `age, sex, bmi, children, smoker, region, charges`), fetched from
[stedy/Machine-Learning-with-R-datasets](https://github.com/stedy/Machine-Learning-with-R-datasets).
It's a real regression dataset for medical insurance charges — directly relevant to
this project's domain, though **it is a general medical-cost dataset, not Chubb's
actual underwriting data**; the model's predictions are illustrative, not a claim
of production-grade actuarial accuracy.

**Method**: 80/20 train/test split (`random_state=42`, 1,070 train / 268 test rows).
Two models trained and evaluated on the same held-out test set —
`backend/ml/train.py`:

| Model | R² (test) | MAE (test) | RMSE (test) |
|---|---|---|---|
| Linear Regression | 0.7836 | $4,181.19 | $5,796.28 |
| Gradient Boosting Regressor | **0.8712** | **$2,486.43** | **$4,471.16** |

**Gradient Boosting Regressor was selected** — it scored higher on every metric on
the real test set (the decision was made from these numbers, not pre-chosen).
Both results are consistent with commonly published benchmarks for this dataset.

**Integration**: `backend/ml/inference.py` loads the persisted model
(`ml/model.joblib`) once and exposes `ml_adjustment(...)`, which predicts annual
charges for a profile and converts them into a bounded premium-loading adjustment
(a scaled, clipped z-score against the training population, capped to
`[-20%, +50%]` so a single prediction can never invert or dominate the premium).
`app/services/scoring.calculate_hybrid_premium` blends this with the existing
deterministic `calculate_risk_coefficient`, and both components are returned
separately in the API response (`rule_based_adjustment`, `ml_predicted_adjustment`,
`ml_predicted_charges`) — the same auditability principle as the rest of this
project: nothing is a black box.

To retrain: `cd backend && python -m ml.train` (regenerates `model.joblib` and
`metrics.json` from `ml/data/insurance.csv`).

## Running via Docker Compose

```bash
docker compose up --build
```

This builds and starts four services: `backend`, `frontend`, `prometheus`, and
`grafana`. The backend runs `alembic upgrade head`, seeds the catalog if empty,
then starts uvicorn with 2 workers; SQLite data persists in the `spre-data` named
volume. The frontend is a multi-stage build: `npm run build` in a `node:20-slim`
stage, served as static files by `nginx:1.27-alpine`. Once up:

- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- Prometheus: http://localhost:9090
- Grafana dashboard: http://localhost:3000/d/spre-backend (anonymous viewer access
  enabled for local convenience; login `admin` / `admin` for edit access)

Verified locally: all four containers build and start cleanly, `/health` returns
`{"status": "ok", "database": "ok"}`, `/api/v1/policies` returns the 20 seeded
policies, and a full request submitted through the React UI in a real browser
against the containerized backend returned 5 ranked recommendations with both a
25.0% rule-based adjustment (smoker) and a 6.5% ML-predicted adjustment blended
into each `final_premium`. Prometheus shows the `spre-backend` scrape target as
`up`, and the Grafana dashboard renders live panels against real traffic generated
during verification. Note: the backend image's build time is dominated by
downloading scikit-learn/pandas/numpy wheels — expect the first `--build` to take
several minutes depending on network conditions; subsequent builds reuse Docker's
layer cache and are fast.

```bash
docker compose down   # stop and remove containers (keeps the named volume)
```

## Testing

### Running the suite

```bash
cd backend
pytest --cov=app --cov-report=term-missing --cov-fail-under=85
```

**Actual result on this machine: 45 tests passed, 95.6% coverage** (gate set at
85%, now covering both `app` and `ml`). Breakdown:

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
- `tests/test_ml_integration.py` — 9 tests: ML inference determinism (same input
  → identical output), no crash on extreme BMI or age-eligibility-boundary inputs,
  a smoker predicted higher than a non-smoker (sanity direction check), and the
  hybrid premium blend (zero ML adjustment matches rule-based-only, positive
  adjustment increases premium, combined coefficient floored at 0.5× base so it
  can never invert, both components reported separately).

Coverage note: `app/seed.py` and `ml/train.py` are excluded from the coverage gate
(`.coveragerc`) — both are one-off scripts exercised manually, not through pytest.
`.coveragerc` also sets `concurrency = greenlet` so coverage.py correctly traces
code that runs across SQLAlchemy's async/greenlet boundary (without it, the async
service layer reports as falsely uncovered).

### Frontend tests

```bash
cd frontend
npm run lint
npm run test
npm run build
```

**Actual result: 10 Vitest tests passed** (`validation.test.ts` — 7 tests mirroring
the backend's Pydantic constraints; `ResultsView.test.tsx` — 3 tests rendering a
mock API response, including the empty-recommendations case and the SVG chart).
Lint (`oxlint`) and the production `vite build` both pass clean.

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

**These numbers are from the current, ML-integrated backend** (re-run after adding
the hybrid premium calculation — the Phase 1, rule-based-only numbers are stale
and superseded; the raw CSVs for both phases are kept in `docs/` for comparison —
`loadtest_default_*` / `loadtest_capacity_*` are Phase 1, `loadtest_ml_default_*` /
`loadtest_ml_capacity_*` are current).

**1. Default configuration** (`RECOMMEND_RATE_LIMIT=20/minute`, the shipped
default) — `docs/loadtest_ml_default_stats.csv`:

| Endpoint | Requests | Failures | p50 | p95 | p99 | Max |
|---|---|---|---|---|---|---|
| POST /api/v1/recommend | 1000 | 960 (96.0%) | 7 ms | 49 ms | 510 ms | 2550 ms |
| GET /api/v1/policies | 208 | 0 | 12 ms | 27 ms | 56 ms | 73 ms |
| GET /health | 199 | 0 | 9 ms | 32 ms | 70 ms | 1127 ms |

As in Phase 1, nearly all `/recommend` failures are genuine `429 Too Many
Requests` from the per-IP rate limiter under single-machine load — expected, not a
defect.

**2. Capacity scenario** (`RECOMMEND_RATE_LIMIT=10000/minute`, limiter effectively
disabled, to isolate the real cost of ML inference in the request path) —
`docs/loadtest_ml_capacity_stats.csv`:

| Endpoint | Requests | Failures | p50 | p95 | p99 | Max |
|---|---|---|---|---|---|---|
| POST /api/v1/recommend | 871 | 18 (2.07%) | 76 ms | 1500 ms | 6100 ms | 7420 ms |
| GET /api/v1/policies | 174 | 0 | 18 ms | 100 ms | 250 ms | 474 ms |
| GET /health | 171 | 0 | 10 ms | 50 ms | 120 ms | 323 ms |

**Honest comparison against Phase 1's capacity run** (rule-based only, no ML):
p50 went from 57ms → 76ms and p95 from 260ms → 1500ms. The ML model call itself is
fast in isolation (a single `predict()` call is low-single-digit milliseconds), but
under 50 concurrent users the CPU-bound scikit-learn inference competes with the
event loop and the tail latency degrades noticeably.

**The 18 failures (2.07%) are real and were investigated, not hidden**: all 18 are
`sqlite3.OperationalError: database is locked`, not application bugs. With request
latency now longer (ML inference in the critical path), the window in which two of
the 2 uvicorn workers try to write to the same SQLite file concurrently
(`recommendation_logs`/`customers` inserts) widens enough that SQLite's
single-writer limitation surfaces under sustained concurrent load. This is a real,
reproducible finding — not a rare fluke — and it's the same limitation already
flagged in this README's "Realistic Scope Statement": SQLite is a dev/demo choice,
and this is a concrete example of the kind of failure a Postgres migration (already
supported by the Postgres-portable SQLAlchemy models) would eliminate. It was not
"fixed" here because doing so honestly (e.g. WAL mode, retry-with-backoff, or
migrating to Postgres) is exactly the kind of production-hardening step this
project's scope statement already defers to a later phase — patching around it
under time pressure would have been worse than reporting it plainly.

Both runs were executed on the same machine (localhost, no network latency) — these
are local capacity numbers, not a claim about production-scale traffic.

## Realistic Scope Statement

This is a solo-built MVP, not a FAANG-scale insurance platform. What's real: a
stateless, containerized, async, rate-limited, input-validated, migration-managed,
load-tested (with real numbers above), ~95%-covered application with an immutable
audit trail and a genuinely trained-and-evaluated ML component. What's *not* built
(and shouldn't be claimed as built): Kubernetes, multi-region deployment,
PostgreSQL read replicas, a Redis cache layer, or a service mesh. Those are
documented here as the natural next steps given the already-stateless backend and
Postgres-portable SQLAlchemy models — not as work that was done. The Phase 2 load
test also surfaced a concrete, reproducible reason a Postgres migration matters
sooner rather than later: SQLite's single-writer limitation under concurrent
writes once request latency increased (see "Load Testing" above).

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
  ml/
    data/insurance.csv        # real public dataset (Medical Cost Personal Datasets)
    train.py                    # trains + evaluates Linear Regression vs Gradient Boosting
    inference.py                  # loads model.joblib, exposes ml_adjustment()
    model.joblib                    # persisted, selected (Gradient Boosting) model
    metrics.json                      # real R²/MAE/RMSE for both candidates
  alembic/                    # migrations (schema is owned here, not hand-edited)
  tests/                         # pytest suite (including test_ml_integration.py)
  locustfile.py                    # load test
  Dockerfile
frontend/
  src/
    api/client.ts        # typed fetch wrapper for the backend REST API
    components/           # RiskProfileForm, ResultsView, ScoreBarChart, validation
    types/api.ts            # TypeScript mirrors of the backend's Pydantic schemas
  Dockerfile               # multi-stage: npm build -> nginx static serve
monitoring/
  prometheus/prometheus.yml            # scrape config targeting backend:8000/metrics
  grafana/provisioning/                # auto-provisioned datasource + dashboard
  grafana/dashboards/spre-dashboard.json
docker-compose.yml
.github/workflows/ci.yml   # backend job + frontend job
docs/                # real load-test CSV output (Phase 1 and post-ML re-run)
```
