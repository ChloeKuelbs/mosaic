"""A deliberately small, source-preserving ClinicalTrials.gov adapter."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional
import re
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

API_URL = "https://clinicaltrials.gov/api/v2/studies"
CONDITION = "postmenopausal osteoporosis"


class Intervention(BaseModel):
    name: str
    type: Optional[str] = None


class Outcome(BaseModel):
    measure: str
    time_frame: Optional[str] = None
    description: Optional[str] = None


class Trial(BaseModel):
    nct_id: str
    source_url: str
    title: Optional[str] = None
    status: Optional[str] = None
    conditions: list[str] = Field(default_factory=list)
    interventions: list[Intervention] = Field(default_factory=list)
    study_type: Optional[str] = None
    phases: list[str] = Field(default_factory=list)
    enrollment: Optional[int] = None
    enrollment_type: Optional[str] = None
    allocation: Optional[str] = None
    masking: Optional[str] = None
    eligibility_sex: Optional[str] = None
    minimum_age: Optional[str] = None
    maximum_age: Optional[str] = None
    eligibility_criteria: Optional[str] = None
    primary_outcomes: list[Outcome] = Field(default_factory=list)
    sponsor: Optional[str] = None
    last_update: Optional[str] = None
    has_results: Optional[bool] = None


class Comparison(BaseModel):
    condition: str = CONDITION
    intervention_query: Optional[str] = None
    retrieved_at: datetime
    total_count: Optional[int] = None
    next_page_token: Optional[str] = None
    trials: list[Trial]
    limitations: str = (
        "Registry metadata, not an assessment of treatment effectiveness or medical advice. "
        "Search matches require eligibility review; trials may differ in populations, design, "
        "and outcomes. Nulls and empty lists mean unreported fields. Has-results indicates "
        "posted registry results; results and effect sizes are not extracted."
    )


def normalize(study: dict[str, Any]) -> Trial:
    protocol = study["protocolSection"]
    identity = protocol["identificationModule"]
    nct_id = identity["nctId"]
    if not re.fullmatch(r"NCT\d{8}", nct_id):
        raise ValueError("Invalid registry identifier")
    design = protocol.get("designModule", {})
    enrollment = design.get("enrollmentInfo", {})
    info = design.get("designInfo", {})
    eligibility = protocol.get("eligibilityModule", {})
    status = protocol.get("statusModule", {})
    return Trial(
        nct_id=nct_id, source_url=f"https://clinicaltrials.gov/study/{nct_id}",
        title=identity.get("briefTitle"), status=status.get("overallStatus"),
        conditions=protocol.get("conditionsModule", {}).get("conditions", []),
        interventions=protocol.get("armsInterventionsModule", {}).get("interventions", []),
        study_type=design.get("studyType"), phases=design.get("phases", []),
        enrollment=enrollment.get("count"), enrollment_type=enrollment.get("type"),
        allocation=info.get("allocation"), masking=info.get("maskingInfo", {}).get("masking"),
        eligibility_sex=eligibility.get("sex"), minimum_age=eligibility.get("minimumAge"),
        maximum_age=eligibility.get("maximumAge"), eligibility_criteria=eligibility.get("eligibilityCriteria"),
        primary_outcomes=[Outcome(measure=o["measure"], time_frame=o.get("timeFrame"),
                                  description=o.get("description"))
                          for o in protocol.get("outcomesModule", {}).get("primaryOutcomes", [])],
        sponsor=protocol.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name"),
        last_update=status.get("lastUpdatePostDateStruct", {}).get("date"),
        has_results=study.get("hasResults"),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": "Mosaic/0.1"}) as client:
        app.state.client = client
        yield


app = FastAPI(title="Mosaic", version="0.1.0", lifespan=lifespan,
              description="Explore source-linked postmenopausal osteoporosis trial metadata.")


STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


def get_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.client


@app.get("/health")
def health():
    """Local liveness only; does not check the registry."""
    return {"status": "ok"}


@app.get("/trials/compare", response_model=Comparison)
async def compare_trials(
    intervention: Optional[str] = Query(None, min_length=1, max_length=200, pattern=r".*\S.*"),
    page_size: int = Query(10, ge=1, le=50),
    page_token: Optional[str] = Query(None, min_length=1, max_length=4096),
    client: httpx.AsyncClient = Depends(get_client),
):
    """Compare one page of registry search matches using consistent fields.

    Reuse the same intervention and page size when following next_page_token.
    Search relevance does not establish clinical eligibility or evidence quality.
    """
    params = {"query.cond": CONDITION, "format": "json", "pageSize": page_size,
              "countTotal": "true", "sort": "@relevance"}
    if intervention:
        params["query.intr"] = intervention.strip()
    if page_token:
        params["pageToken"] = page_token
    try:
        response = await client.get(API_URL, params=params)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "ClinicalTrials.gov timed out. Please retry.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, "ClinicalTrials.gov is unavailable or rejected the request.") from exc
    try:
        payload = response.json()
        return Comparison(
            intervention_query=intervention.strip() if intervention else None,
            retrieved_at=datetime.now(timezone.utc), total_count=payload.get("totalCount"),
            next_page_token=payload.get("nextPageToken"),
            trials=[normalize(study) for study in payload["studies"]],
        )
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise HTTPException(502, "ClinicalTrials.gov returned an unexpected response.") from exc
