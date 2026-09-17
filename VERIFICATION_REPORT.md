# SPRE Build Verification Report

## Summary
28/29 items DONE, 1 PARTIAL, 0 NOT DONE

## Detailed Results

### 1. Repo structure
1. [DONE] `backend/`, `frontend/`, `tests/`, `alembic/` directories exist with real content (not empty stubs) — `find backend -maxdepth 2 -type d -not -path "*/venv*"` shows `backend/alembic`, `backend/alembic/versions`, `backend/app`, `backend/app/routers`, `backend/app/services`, `backend/tests`; `find backend/tests -type f` shows `conftest.py`, `test_api.py`, `test_scoring.py`, `__init__.py` (all non-empty, real test code); `find backend/alembic -type f` shows `env.py`, `script.py.mako`, and two real revision files under `versions/`; `find frontend -maxdepth 1 -type f` shows `app.py`, `Dockerfile`, `requirements.txt`, `.env.example`, `.dockerignore`.
2. [DONE] `README.md` exists — `wc -l README.md` → `354 README.md`. `grep -n "^#" README.md` shows real sections: `## Architecture`, `### Request flow for POST /api/v1/recommend`, `## Tech Stack`, `## Database Schema`, `## API Surface`, `## Non-Functional Requirements`, `## Running Locally (without Docker)`, `## Running via Docker Compose`, `## Testing`, `## Load Testing`, `## Project Structure` — setup, architecture, and test commands are all documented.

### 2. Database
3. [DONE] All 3 tables exist with the exact columns specified — verified via `sqlite3.connect('spre.db')` + `SELECT sql FROM sqlite_master` (not the migration file) on a freshly `alembic upgrade head`'d database:
   ```
   CREATE TABLE policies (
       policy_id INTEGER NOT NULL, policy_name VARCHAR(100) NOT NULL, policy_type VARCHAR(30) NOT NULL,
       description TEXT, base_premium NUMERIC(10, 2) NOT NULL, min_age INTEGER, max_age INTEGER,
       min_income NUMERIC(12, 2), coverage_amount NUMERIC(15, 2) NOT NULL, is_active BOOLEAN,
       created_at DATETIME DEFAULT (CURRENT_TIMESTAMP), PRIMARY KEY (policy_id)
   )
   CREATE TABLE customers (
       customer_id INTEGER NOT NULL, full_name VARCHAR(100) NOT NULL, age INTEGER NOT NULL,
       monthly_income NUMERIC(12, 2) NOT NULL, occupation VARCHAR(50), is_smoker BOOLEAN,
       has_chronic_illness BOOLEAN, owns_vehicle BOOLEAN, vehicle_value NUMERIC(12, 2),
       owns_property BOOLEAN, property_value NUMERIC(15, 2), created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
       PRIMARY KEY (customer_id)
   )
   CREATE TABLE recommendation_logs (
       log_id INTEGER NOT NULL, customer_id INTEGER NOT NULL, policy_id INTEGER NOT NULL,
       calculated_suitability_score NUMERIC(5, 2) NOT NULL, final_premium_quoted NUMERIC(10, 2) NOT NULL,
       recommendation_rank INTEGER NOT NULL, generated_reasoning TEXT, created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
       PRIMARY KEY (log_id), FOREIGN KEY(customer_id) REFERENCES customers (customer_id),
       FOREIGN KEY(policy_id) REFERENCES policies (policy_id)
   )
   ```
   (SQLite stores SQLAlchemy's `Numeric(p,s)` as `NUMERIC(p,s)` — functionally identical to `DECIMAL(p,s)` in the spec, same storage class in SQLite.)
4. [DONE] Both indexes exist — checked via `SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index'` (direct DB inspection, not the migration file):
   ```
   ('idx_policy_filter', 'policies', 'CREATE INDEX idx_policy_filter ON policies (policy_type, min_age, max_age)')
   ('idx_logs_customer', 'recommendation_logs', 'CREATE INDEX idx_logs_customer ON recommendation_logs (customer_id)')
   ```
5. [DONE] Policies table seeded — real query output: `row count: 20`, `by type: [('AUTO', 5), ('HEALTH', 5), ('LIFE', 5), ('PROPERTY', 5)]`, sample: `[(1, 'Basic Health Shield', 'HEALTH'), (2, 'Comprehensive Health Plus', 'HEALTH'), (3, 'Senior Care Health', 'HEALTH'), (4, 'Family Health Guard', 'HEALTH'), (5, 'Critical Illness Cover', 'HEALTH')]`.

### 3. API
6. [DONE] All 5 endpoints exist and were hit live in item 7 below: `POST /api/v1/recommend`, `GET /api/v1/policies`, `GET /api/v1/recommendations/{customer_id}`, `GET /health`, `GET /metrics`.
7. [DONE] Server started (`uvicorn app.main:app --host 127.0.0.1 --port 8000`), each endpoint hit for real with curl:
   - `GET /health` → `STATUS:200` `{"status":"ok","database":"ok"}`
   - `GET /api/v1/policies` → `STATUS:200`, real JSON array starting `[{"policy_id":1,"policy_name":"Basic Health Shield",...}]`
   - `POST /api/v1/recommend` (valid payload) → `STATUS:200`, `{"customer_id":1,"recommendations":[{"rank":1,"policy_id":6,"policy_name":"Comprehensive Auto Shield","policy_type":"AUTO","suitability_score":75.0,"final_premium":1450.0,"reasoning":"Vehicle ownership and value increased suitability."},...]}`
   - `GET /api/v1/recommendations/1` → `STATUS:200`, real 5-row audit-log JSON array matching the recommend response
   - `GET /metrics` → `STATUS:200`, real Prometheus exposition text (see item 22)
8. [DONE] Invalid payload (`age: 200`) → `STATUS:422`, `{"detail":[{"type":"less_than_equal","loc":["body","age"],"msg":"Input should be less than or equal to 100","input":200,"ctx":{"le":100}}]}`.

### 4. Business logic
9. [DONE] Scoring/premium functions are standalone, isolated callables in `app/services/scoring.py`, not inlined in the route — `grep -n "^def "` shows:
   ```
   def score_policy(profile: RiskProfileRequest, policy_type: str) -> ScoreResult:
   def calculate_risk_coefficient(profile: RiskProfileRequest) -> float:
   def calculate_premium(base_premium: float, profile: RiskProfileRequest) -> float:
   def is_eligible(profile: RiskProfileRequest, min_age: int, max_age: int, min_income: float) -> bool:
   ```
   These are imported by `app/services/recommender.py`, which is imported by `app/routers/recommend.py` — no scoring/premium logic is written directly inside the route function.
10. [DONE] Ran `pytest tests/test_scoring.py -v` right now:
    ```
    collecting ... collected 23 items

    tests/test_scoring.py::TestEligibility::test_within_range_is_eligible PASSED [  4%]
    tests/test_scoring.py::TestEligibility::test_below_min_age_is_ineligible PASSED [  8%]
    tests/test_scoring.py::TestEligibility::test_above_max_age_is_ineligible PASSED [ 13%]
    tests/test_scoring.py::TestEligibility::test_below_min_income_is_ineligible PASSED [ 17%]
    tests/test_scoring.py::TestEligibility::test_boundary_ages_are_eligible PASSED [ 21%]
    tests/test_scoring.py::TestRiskCoefficient::test_baseline_coefficient_is_one PASSED [ 26%]
    tests/test_scoring.py::TestRiskCoefficient::test_smoker_adds_expected_loading PASSED [ 30%]
    tests/test_scoring.py::TestRiskCoefficient::test_hazardous_occupation_adds_expected_loading PASSED [ 34%]
    tests/test_scoring.py::TestRiskCoefficient::test_chronic_illness_adds_expected_loading PASSED [ 39%]
    tests/test_scoring.py::TestRiskCoefficient::test_unemployed_adds_expected_loading PASSED [ 43%]
    tests/test_scoring.py::TestRiskCoefficient::test_multiple_risk_factors_stack PASSED [ 47%]
    tests/test_scoring.py::TestPremiumCalculator::test_zero_base_premium_yields_zero PASSED [ 52%]
    tests/test_scoring.py::TestPremiumCalculator::test_baseline_premium_unchanged PASSED [ 56%]
    tests/test_scoring.py::TestPremiumCalculator::test_smoker_premium_loaded PASSED [ 60%]
    tests/test_scoring.py::TestPremiumCalculator::test_stacked_risk_premium_loaded PASSED [ 65%]
    tests/test_scoring.py::TestScoringEngine::test_health_score_penalizes_smoker PASSED [ 69%]
    tests/test_scoring.py::TestScoringEngine::test_health_score_penalizes_chronic_illness PASSED [ 73%]
    tests/test_scoring.py::TestScoringEngine::test_auto_score_rewards_vehicle_ownership PASSED [ 78%]
    tests/test_scoring.py::TestScoringEngine::test_property_score_rewards_property_ownership PASSED [ 82%]
    tests/test_scoring.py::TestScoringEngine::test_life_score_penalizes_smoker_and_chronic_illness PASSED [ 86%]
    tests/test_scoring.py::TestScoringEngine::test_score_is_clamped_between_zero_and_hundred PASSED [ 91%]
    tests/test_scoring.py::TestScoringEngine::test_unknown_policy_type_falls_back_to_default_score PASSED [ 95%]
    tests/test_scoring.py::TestScoringEngine::test_reasoning_is_nonempty_string PASSED [100%]

    ============================= 23 passed in 3.13s ==============================
    ```

### 5. Concurrency
11. [DONE] Routes are `async def` — `grep -n "async def" app/routers/*.py`:
    ```
    app/routers/health.py:12:async def health(db: AsyncSession = Depends(get_db)):
    app/routers/recommend.py:30:async def recommend(
    app/routers/recommend.py:42:async def list_policies(db: AsyncSession = Depends(get_db)):
    app/routers/recommend.py:49:async def get_recommendations_for_customer(
    ```
12. [PARTIAL] DB engine has explicit pool-config code, but it is **not active** on the database this project actually runs against. Source (`app/database.py`):
    ```python
    engine_kwargs: dict = {"connect_args": connect_args, "pool_pre_ping": True}
    if "sqlite" not in DATABASE_URL:
        engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "10"))
        engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "5"))
    ```
    Empirically confirmed live, against the actual default runtime config:
    ```
    DATABASE_URL: sqlite+aiosqlite:///./spre.db
    pool class: NullPool
    has size(): False
    ```
    The `pool_size`/`max_overflow` branch is gated by `if "sqlite" not in DATABASE_URL`, and this project's only configured database is SQLite. So the engine actually runs on `NullPool` with no configured pool size at all — the explicit pool-size code exists and would activate on a Postgres URL, but on the database path this project ships and runs on today, it is dead code, not a config that is "actually active on the runtime database this project uses."
13. [DONE] No global mutable request state — `grep -n "^[a-zA-Z_]* = \[\]\|^[a-zA-Z_]* = {}\|^[a-zA-Z_]* = dict(\|global "` across `app/*.py app/routers/*.py app/services/*.py` returned no matches.

### 6. Security
14. [DONE] No raw string-formatted SQL — `grep -rn 'f"SELECT\|f"INSERT\|f"UPDATE\|f"DELETE\|\.format(.*SELECT\|% .*SELECT' app/` returned no matches.
15. [DONE] CORS explicit allow-list, not `*` — `app/main.py`:
    ```
    allowed_origins = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:8501").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
    ```
16. [DONE] Rate limiting tested live: 25 rapid `POST /api/v1/recommend` calls against a running server →
    ```
    200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 200 429 429 429 429 429 429
    ```
    429s confirmed real, not assumed from reading the decorator.
17. [DONE] No hardcoded secrets — `grep -rniE "(password|secret|api_key|apikey)\s*=\s*['\"][a-zA-Z0-9]" app/` returned no matches.
18. [DONE] `pip-audit -r requirements.txt` run live just now:
    ```
    No known vulnerabilities found
    ```

### 7. Testing
19. [DONE] Full suite run right now:
    ```
    tests\test_api.py .............                                          [ 36%]
    tests\test_scoring.py .......................                            [100%]

    ---------- coverage: platform win32, python 3.12.3-final-0 -----------
    Name                          Stmts   Miss  Cover   Missing
    -----------------------------------------------------------
    app\__init__.py                   0      0   100%
    app\database.py                  15      4    73%   12-13, 25-26
    app\logging_config.py            10      0   100%
    app\main.py                      25      3    88%   23-25
    app\models.py                    45      0   100%
    app\routers\__init__.py           0      0   100%
    app\routers\health.py            14      2    86%   16-17
    app\routers\recommend.py         34      0   100%
    app\schemas.py                   50      0   100%
    app\services\__init__.py          0      0   100%
    app\services\recommender.py      30      0   100%
    app\services\scoring.py          73      6    92%   69-70, 83-84, 97-98
    -----------------------------------------------------------
    TOTAL                           296     15    95%

    Required test coverage of 85% reached. Total coverage: 94.93%

    ============================= 36 passed in 6.52s ==============================
    ```
20. [DONE] `backend/locustfile.py` exists (1,277 bytes) AND was actually executed — real recorded output files exist on disk with real filesystem timestamps (not fabricated numbers):
    ```
    -rw-r--r-- 1 KIIT0001 197609 852 Sep 17 00:47 docs/loadtest_default_stats.csv
    -rw-r--r-- 1 KIIT0001 197609 843 Sep 17 00:49 docs/loadtest_capacity_stats.csv
    ```
    Real content, default rate-limited config:
    ```
    Type,Name,Request Count,Failure Count,Median Response Time,...,50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%
    GET,/api/v1/policies,195,0,9,...,9,10,11,12,14,18,22,35,38,38,38
    POST,/api/v1/recommend,985,945,5,...,5,6,7,8,10,26,110,180,1100,1100,1100
    GET,/health,205,0,7,...,7,8,9,10,12,15,37,40,890,890,890
    ,Aggregated,1385,945,6,...,6,7,8,9,12,22,62,150,1100,1100,1100
    ```
    Real content, capacity scenario (rate limit raised):
    ```
    Type,Name,Request Count,Failure Count,Median Response Time,...,50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%
    GET,/api/v1/policies,225,0,15,...,15,18,22,23,38,50,88,100,240,240,240
    POST,/api/v1/recommend,936,0,57,...,57,82,100,120,190,260,430,600,960,960,960
    GET,/health,183,0,10,...,10,12,14,14,17,21,29,33,36,36,36
    ,Aggregated,1344,0,41,...,41,60,79,92,150,220,360,540,910,960,960
    ```

### 8. Observability
21. [DONE] `/health` real response: `{"status":"ok","database":"ok"}` (STATUS:200) — includes a live DB connectivity check, not a hardcoded string.
22. [DONE] `/metrics` real Prometheus output snippet:
    ```
    # HELP python_gc_objects_collected_total Objects collected during gc
    # TYPE python_gc_objects_collected_total counter
    python_gc_objects_collected_total{generation="0"} 2810.0
    python_gc_objects_collected_total{generation="1"} 2725.0
    python_gc_objects_collected_total{generation="2"} 395.0
    ```
23. [DONE] Structured JSON logging — real log line captured from an actual `/api/v1/recommend` request during this audit:
    ```
    {"asctime": "2026-09-17 18:12:31,194", "name": "spre.recommend", "levelname": "INFO", "message": "recommendation_generated", "taskName": "Task-15", "customer_id": 1, "num_recommendations": 5}
    ```

### 9. Containerization
24. [DONE] `backend/Dockerfile` (262 bytes), `frontend/Dockerfile` (227 bytes), `docker-compose.yml` (1,116 bytes) all exist.
25. [DONE] Ran `docker compose up --build -d` live just now (Docker Desktop was not running at audit start — started it, waited for readiness, then ran):
    ```
    smartpolicyrecommendationengine-backend  Built
    smartpolicyrecommendationengine-frontend  Built
    Container smartpolicyrecommendationengine-backend-1  Started
    Container smartpolicyrecommendationengine-prometheus-1  Started
    Container smartpolicyrecommendationengine-frontend-1  Started
    Container smartpolicyrecommendationengine-grafana-1  Started
    ```
    Confirmed all 4 containers `Up`:
    ```
    NAME                                           STATUS
    smartpolicyrecommendationengine-backend-1      Up 11 seconds
    smartpolicyrecommendationengine-frontend-1     Up 11 seconds
    smartpolicyrecommendationengine-grafana-1      Up 10 seconds
    smartpolicyrecommendationengine-prometheus-1   Up 11 seconds
    ```
    `curl http://localhost:8000/health` against the containerized backend → `{"status":"ok","database":"ok"}`. Torn down afterward with `docker compose down`.

### 10. CI config
26. [DONE] `.github/workflows/ci.yml` exists (949 bytes), contains lint (ruff), format check (black), test+coverage gate (pytest), pip-audit, and a Docker build step.
27. [DONE] Ran the exact lint/format commands from the workflow manually, right now:
    ```
    All checks passed!
    ruff exit: 0
    All done! ✨ 🍰 ✨
    17 files would be left unchanged.
    black exit: 0
    ```
    The workflow's `pytest --cov=app --cov-report=term-missing --cov-fail-under=85` and `pip-audit -r requirements.txt` commands are the same ones already run and pasted in items 19 and 18 above (both passed).

### 11. GitHub
28. [DONE] Repo is pushed — `git remote -v`:
    ```
    origin	https://github.com/rachitkumar2105/Smart-Policy-Recommendation-Engine.git (fetch)
    origin	https://github.com/rachitkumar2105/Smart-Policy-Recommendation-Engine.git (push)
    ```
    `git fetch origin` then compared SHAs:
    ```
    HEAD:        b6206a81244213fa54af93ce5ec0ac99f96ddffa
    origin/main: b6206a81244213fa54af93ce5ec0ac99f96ddffa
    MATCH: identical commit SHA
    ```
29. [DONE] No deployment anywhere — scoped filesystem search (excluding `venv`/`.git`) for `render.yaml`, `railway.json`, `Procfile`, `fly.toml`, `vercel.json` returned nothing. `grep -niE "deploy|render\.com|railway\.app|streamlit\.io|fly\.io|vercel" .github/workflows/ci.yml` → "no deploy-related job found in ci.yml". No deploy config or CI deploy job exists anywhere in the repo.

## Known gaps
- **Item 12 (PARTIAL)**: The DB engine's explicit `pool_size`/`max_overflow` configuration is real code, but it is wrapped in `if "sqlite" not in DATABASE_URL:` — and SQLite is the only database this project is configured to run against. Empirically confirmed live: with the project's actual `DATABASE_URL`, the engine uses `NullPool` and reports `has size(): False`. The pool-size config would take effect if `DATABASE_URL` were switched to Postgres, but as shipped and run today, it is inactive/dead code on the runtime path — not a gap in intent, but a real gap between "explicit pool configuration" and "explicit pool configuration that is actually active."
