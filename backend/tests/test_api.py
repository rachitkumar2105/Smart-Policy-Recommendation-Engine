import pytest

VALID_PROFILE = {
    "full_name": "Jane Doe",
    "age": 30,
    "monthly_income": 50000,
    "occupation": "DESK_JOB",
    "is_smoker": False,
    "has_chronic_illness": False,
    "owns_vehicle": True,
    "vehicle_value": 800000,
    "owns_property": False,
    "property_value": 0,
}


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


@pytest.mark.asyncio
async def test_list_policies_empty_when_none_seeded(client):
    resp = await client.get("/api/v1/policies")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_policies_returns_seeded_policy(client, seeded_policy):
    resp = await client.get("/api/v1/policies")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["policy_name"] == "Test Auto Policy"


@pytest.mark.asyncio
async def test_recommend_returns_eligible_policy(client, seeded_policy):
    resp = await client.post("/api/v1/recommend", json=VALID_PROFILE)
    assert resp.status_code == 200
    body = resp.json()
    assert body["customer_id"] == 1
    assert len(body["recommendations"]) == 1
    rec = body["recommendations"][0]
    assert rec["policy_name"] == "Test Auto Policy"
    assert rec["rank"] == 1
    assert rec["final_premium"] == 1000.0


@pytest.mark.asyncio
async def test_recommend_excludes_ineligible_age(client, seeded_policy):
    profile = {**VALID_PROFILE, "age": 18}  # policy requires min_age=21
    resp = await client.post("/api/v1/recommend", json=profile)
    assert resp.status_code == 200
    assert resp.json()["recommendations"] == []


@pytest.mark.asyncio
async def test_recommend_excludes_below_min_income(client, seeded_policy):
    profile = {
        **VALID_PROFILE,
        "monthly_income": 500,
    }  # policy requires min_income=10000
    resp = await client.post("/api/v1/recommend", json=profile)
    assert resp.status_code == 200
    assert resp.json()["recommendations"] == []


@pytest.mark.asyncio
async def test_recommend_no_matching_policies_when_catalog_empty(client):
    resp = await client.post("/api/v1/recommend", json=VALID_PROFILE)
    assert resp.status_code == 200
    body = resp.json()
    assert body["recommendations"] == []


@pytest.mark.asyncio
async def test_recommend_rejects_invalid_age(client):
    profile = {**VALID_PROFILE, "age": 5}
    resp = await client.post("/api/v1/recommend", json=profile)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_recommend_rejects_negative_income(client):
    profile = {**VALID_PROFILE, "monthly_income": -100}
    resp = await client.post("/api/v1/recommend", json=profile)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_recommend_rejects_invalid_occupation(client):
    profile = {**VALID_PROFILE, "occupation": "ASTRONAUT"}
    resp = await client.post("/api/v1/recommend", json=profile)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_recommend_persists_audit_log(client, seeded_policy):
    resp = await client.post("/api/v1/recommend", json=VALID_PROFILE)
    customer_id = resp.json()["customer_id"]

    audit_resp = await client.get(f"/api/v1/recommendations/{customer_id}")
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) == 1
    assert logs[0]["policy_id"] == seeded_policy.policy_id
    assert logs[0]["recommendation_rank"] == 1


@pytest.mark.asyncio
async def test_audit_trail_404_for_unknown_customer(client):
    resp = await client.get("/api/v1/recommendations/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_metrics_endpoint_exposed(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert b"python_gc_objects_collected_total" in resp.content
