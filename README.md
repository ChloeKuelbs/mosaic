# Mosaic

Mosaic is a women’s health evidence explorer, starting with **postmenopausal osteoporosis**. This version includes a FastAPI backend and a responsive browser interface that searches ClinicalTrials.gov and displays trial records in a consistent, source-linked shape for comparison.

The goal is to make study populations, interventions, designs, and outcomes easier to inspect. It does not rank treatments, calculate treatment effects, or offer medical advice. Registry entries are submitted records, not independently verified conclusions or a complete systematic review.

https://mosaic-0mbm.onrender.com

## Run locally

Python 3.9+ is required. No API key or database is needed. Internet access is required for registry searches.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 for the explorer, or http://127.0.0.1:8000/docs for interactive API documentation.

In the explorer, search an intervention (or leave it blank), select up to three trials, and scroll to the side-by-side comparison. Load more results without losing your selections. Starting a new search clears the selection. Expand eligibility criteria in the comparison and use the NCT links to inspect original records. Loading, empty, and retryable error states are shown explicitly.

The frontend is plain HTML/CSS/JavaScript served by FastAPI; there is no separate frontend installation or build step. Fonts use Google Fonts with system fallbacks.

```sh
curl 'http://127.0.0.1:8000/trials/compare?intervention=alendronate&page_size=5'
curl 'http://127.0.0.1:8000/health'
```

## API

`GET /trials/compare` returns one page of trials with identical comparison fields:

- `intervention`: optional registry intervention query, up to 200 characters.
- `page_size`: 1–50, default 10.
- `page_token`: opaque cursor returned as `next_page_token`; send it unchanged with the same search parameters to retrieve the next page.

The backend always sends `query.cond=postmenopausal osteoporosis` to the [ClinicalTrials.gov v2 studies API](https://clinicaltrials.gov/data-api/api), optionally adds `query.intr`, and requests relevance ordering. These use the registry's search semantics. A match does **not** prove every participant is postmenopausal or that the study is appropriate for a particular person. Review `eligibility_criteria` and the source record.

Each trial includes its NCT identifier, direct source URL, title, status, conditions, interventions, phase, study type, allocation, masking, enrollment and enrollment type, eligibility, primary outcomes with time frames, sponsor, last registry update, and whether registry results are posted. `retrieved_at` records the UTC retrieval time; `total_count` and `next_page_token` describe the registry search, not an exhaustive evidence review.

Missing scalar fields are `null`; missing collections are `[]`. Enrollment can be estimated or actual. Outcome measures describe what a trial measures, not observed results. `has_results` is registry availability metadata; this version does not extract results or effect sizes. No generated clinical summaries are added.

Invalid parameters return 422. Registry/network failures return 502; timeouts return 504. Malformed registry records fail the response rather than silently disappearing. `/health` checks local liveness only.

## Tests

```sh
python -m pytest -q
```

Tests use an HTTP mock and synthetic records, so they run offline and deterministically. They exercise request scoping and cursor forwarding, mapping of design/enrollment/outcome fields, source-link construction, missing values, empty searches, input bounds, upstream failures, timeouts, and malformed records. These verify the adapter contract; they do not measure search recall or clinical relevance.

For a manual live integration check, run the server and the search curl above. Confirm that source links resolve and compare returned fields with the registry record. Registry contents can change, so live results are not pinned test fixtures.

## Scope and structure

`app/main.py` contains typed response models, a registry-to-comparison mapper, and the API. One lifespan-managed asynchronous HTTP client provides connection reuse and a 15-second network timeout. The registry destination is fixed. Responses are fetched on demand, with no persistence, authentication, or background ingestion in this first version. Do not expose it publicly without deployment-specific access controls and traffic limits.

`app/static/` holds the interface. Registry content is inserted as text, not HTML. The interface shares the API origin and needs no CORS configuration.

`tests/test_api.py` covers the API through FastAPI's test client and an injected HTTP transport. Future work can add selected-trial comparisons, published evidence, and explicit evidence-quality assessments after the registry contract is validated.


## Ask Mosaic — optional grounded AI analysis

Select one to three trials and use **Ask Mosaic** to ask about their registry-described study design, eligibility, enrollment, or primary outcomes. The server fetches each selected NCT record from ClinicalTrials.gov directly before calling the language model. The model sees only bounded, whitelisted metadata; returned citation IDs are validated against the selected NCT identifiers. **These checks do not independently establish factual entailment of every claim.** Treat all AI responses as hypotheses to verify against the linked registry records.

This is **not** treatment advice, evidence synthesis, systematic review, or clinical decision support. Registered outcome measures do not establish efficacy. AI answers are not independently verified and may contain errors.

The feature is disabled unless you set `OPENAI_API_KEY` in your **Render service environment settings** (or your local shell). Never commit API keys to GitHub, put them in frontend JavaScript, or paste them into the app. Render's production and development services require separate configuration if both should have AI enabled.

Optional environment variables:
- `MOSAIC_AI_MODEL`: default `gpt-4o-mini` (the configured OpenAI account must have model access).
- `MOSAIC_AI_PER_IP_HOURLY`: default `5`.
- `MOSAIC_AI_DAILY_LIMIT`: default `40`.

**Cost and abuse warning:** Each successful AI request uses paid OpenAI API tokens. The included quotas are lightweight, in-memory per-process guards, *not* production-grade rate limits; they reset on restart and don't coordinate across instances. For a public site, set a strict provider budget and add edge rate limiting or authentication before advertising the feature widely. If the key is absent, `POST /ai/ask` returns 503 while the trial search remains usable.

Example POST body: `{"question":"How do these studies differ in design?","nct_ids":["NCT00000001"]}` using an actual valid registry ID. The endpoint validates inputs and fetches fresh source records; it never accepts client-supplied evidence.

## Public and development hosting (Render)

The root `render.yaml` defines two free Python web services:

| Service | Git branch | Purpose |
| --- | --- | --- |
| `mosaic` | `main` | Public, stable version |
| `mosaic-dev` | `dev` | Testing upcoming changes |

Both deploy after GitHub checks pass, use `/health` for health checks, and run the UI and API together. `.python-version` selects Python 3.13. Service URLs are assigned by Render; names are subject to availability. Both URLs are public: the development service is **not password-protected**. Do not place private data or secrets in either site's content.

To deploy, connect GitHub in Render, choose **New → Blueprint**, select `ChloeKuelbs/mosaic` and its `main` branch, and review the two free services before creating the Blueprint. The `dev` branch must exist before deployment. After both deploy successfully, open each service's assigned URL. Test an intervention search and verify `/health` returns `{"status":"ok"}`.

Work on `dev`, push changes to preview them on the development site, then open a pull request from `dev` to `main`. Merging updates the public site after checks pass. Avoid direct feature changes on `main`.

Free services sleep when idle and share workspace usage allowances; expect a slower first request after inactivity. See [Render free-service limits](https://render.com/docs/free). An always-on plan or development-site authentication can be added later.
