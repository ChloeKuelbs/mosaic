"""Contract tests for the optional AI endpoint (no network or API charges)."""
import json

from fastapi.testclient import TestClient
from app.main import app
from app import ai


def test_ai_not_configured(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(app) as client:
        res = client.post("/ai/ask", json={"question": "What are the differences?", "nct_ids": ["NCT00000001"]})
    assert res.status_code == 503


def test_ai_rejects_invalid_identifiers(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    with TestClient(app) as client:
        for ids in [["invalid"], ["NCT00000001", "NCT00000001"], []]:
            res = client.post("/ai/ask", json={"question": "Compare study designs", "nct_ids": ids})
            assert res.status_code == 422


def test_ai_rejects_nonquestions(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    with TestClient(app) as client:
        res = client.post("/ai/ask", json={"question": "12345678", "nct_ids": ["NCT00000001"]})
    assert res.status_code == 422


def test_summary_preserves_source_identity():
    summary, source = ai._record_summary(
        {"protocolSection": {"identificationModule": {"nctId": "NCT00000001", "briefTitle": "Example"},
                             "designModule": {"enrollmentInfo": {"count": 20}},
                             "outcomesModule": {"primaryOutcomes": [{"measure": "Density", "timeFrame": "1 year"}]}}},
        "NCT00000001"
    )
    assert summary["enrollment"]["count"] == 20
    assert summary["primary_outcomes"][0]["measure"] == "Density"
    assert source.url == "https://clinicaltrials.gov/study/NCT00000001"
