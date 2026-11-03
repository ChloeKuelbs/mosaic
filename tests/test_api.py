"""Offline contract tests with synthetic registry records; no clinical claims."""
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import app, get_client


@pytest.fixture
def registry():
    state = {"payload": {"studies": []}, "status": 200, "requests": []}

    def respond(request):
        state["requests"].append(request)
        if state.get("timeout"):
            raise httpx.ReadTimeout("simulated", request=request)
        return httpx.Response(state["status"], json=state["payload"])

    async def override():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            yield client

    app.dependency_overrides[get_client] = override
    with TestClient(app) as client:
        yield client, state
    app.dependency_overrides.clear()


def test_mapping_provenance_and_pagination(registry):
    client, state = registry
    state["payload"] = {
        "totalCount": 2, "nextPageToken": "cursor",
        "studies": [{"hasResults": False, "protocolSection": {
            "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Synthetic trial"},
            "designModule": {"studyType": "INTERVENTIONAL", "phases": ["PHASE3"],
                             "enrollmentInfo": {"count": 120, "type": "ESTIMATED"},
                             "designInfo": {"allocation": "RANDOMIZED", "maskingInfo": {"masking": "DOUBLE"}}},
            "armsInterventionsModule": {"interventions": [{"name": "Example", "type": "DRUG", "description": "extra"}]},
            "eligibilityModule": {"sex": "FEMALE", "minimumAge": "50 Years", "eligibilityCriteria": "Postmenopausal"},
            "outcomesModule": {"primaryOutcomes": [{"measure": "BMD change", "timeFrame": "12 months"}]},
            "statusModule": {"overallStatus": "COMPLETED", "lastUpdatePostDateStruct": {"date": "2025-01-01"}},
        }}],
    }
    response = client.get("/trials/compare", params={"intervention": " Example ", "page_size": 2, "page_token": "previous"})
    assert response.status_code == 200
    body = response.json()
    trial = body["trials"][0]
    assert trial["source_url"] == "https://clinicaltrials.gov/study/NCT00000001"
    assert trial["enrollment"] == 120 and trial["enrollment_type"] == "ESTIMATED"
    assert trial["primary_outcomes"][0]["time_frame"] == "12 months"
    assert trial["masking"] == "DOUBLE" and trial["has_results"] is False
    assert trial["eligibility_criteria"] == "Postmenopausal"
    assert body["next_page_token"] == "cursor" and body["total_count"] == 2
    assert body["retrieved_at"].endswith("Z")
    params = state["requests"][0].url.params
    assert params["query.cond"] == "postmenopausal osteoporosis"
    assert params["query.intr"] == "Example"
    assert params["pageToken"] == "previous" and params["pageSize"] == "2"


def test_missing_fields_remain_unknown(registry):
    client, state = registry
    state["payload"] = {"studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT00000002"}}}]}
    trial = client.get("/trials/compare").json()["trials"][0]
    assert trial["enrollment"] is None and trial["has_results"] is None
    assert trial["interventions"] == [] and trial["primary_outcomes"] == []


def test_empty_search(registry):
    client, _ = registry
    body = client.get("/trials/compare").json()
    assert body["trials"] == [] and body["next_page_token"] is None


@pytest.mark.parametrize("params", [{"page_size": 0}, {"page_size": 51}, {"intervention": " "}, {"page_token": ""}])
def test_validation_prevents_upstream_calls(registry, params):
    client, state = registry
    assert client.get("/trials/compare", params=params).status_code == 422
    assert state["requests"] == []


@pytest.mark.parametrize("status", [400, 429, 500])
def test_upstream_errors(registry, status):
    client, state = registry
    state["status"] = status
    assert client.get("/trials/compare").status_code == 502


def test_timeout(registry):
    client, state = registry
    state["timeout"] = True
    assert client.get("/trials/compare").status_code == 504


@pytest.mark.parametrize("payload", [{}, {"studies": None}, {"studies": [{}]}, {"studies": [{"protocolSection": {"identificationModule": {"nctId": "bad"}}}]}])
def test_malformed_upstream_is_not_silently_dropped(registry, payload):
    client, state = registry
    state["payload"] = payload
    assert client.get("/trials/compare").status_code == 502


def test_health(registry):
    client, state = registry
    assert client.get("/health").json() == {"status": "ok"}
    assert state["requests"] == []


def test_explorer_and_assets_served(registry):
    client, state = registry
    page = client.get("/")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert 'href="/explore/bone-health"' in page.text
    assert 'href="/wellbeing"' in page.text
    assert 'id="search-form"' in client.get('/explore/bone-health').text
    assert 'id="comparison-table"' in client.get('/explore/bone-health').text
    for asset, content_type in [("app.js", "javascript"), ("styles.css", "text/css")]:
        response = client.get(f"/static/{asset}")
        assert response.status_code == 200
        assert content_type in response.headers["content-type"]
    assert client.get("/static/missing.css").status_code == 404
    assert state["requests"] == []

def test_topic_catalog_and_page_routes(registry):
    client, state = registry
    topics = client.get("/api/topics").json()
    assert len(topics) == 6
    assert {t["slug"] for t in topics} == {"bone-health", "endometriosis", "pmdd", "postpartum-depression", "pcos", "menopause"}
    for t in topics:
        assert client.get("/explore/" + t["slug"]).status_code == 200
    assert client.get("/wellbeing").status_code == 200
    assert client.get("/explore/not-a-topic").status_code == 404
    assert client.get("/api/topics/not-a-topic").status_code == 404
    assert client.get("/api/topics/not-a-topic/literature").status_code == 404
    assert state["requests"] == []


def test_topic_specific_trial_query(registry):
    client, state = registry
    client.get("/trials/compare", params={"topic":"endometriosis"})
    assert state["requests"][0].url.params["query.cond"] == "endometriosis"
    assert client.get("/trials/compare", params={"topic":"invalid"}).status_code == 422


def test_wellbeing_validation(registry):
    client, state = registry
    for params in [{"age":"17-18"},{"domain":"miracle cures"},{"life_stage":"other"},{"limit":100}]:
        assert client.get("/api/wellbeing/literature", params=params).status_code == 422
    assert state["requests"] == []
