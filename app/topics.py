"""Women's health topic catalog and recent PubMed literature (not a systematic review)."""
from datetime import datetime, timezone
import re
import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()
TOPICS = {
 "bone-health": {"name":"Bone health & osteoporosis","short":"Bone density, fracture prevention, and treatment research","category":"Musculoskeletal health","condition":"postmenopausal osteoporosis","pubmed":"(osteoporosis OR bone mineral density) AND (women OR postmenopausal)","accent":"sage","examples":["alendronate","denosumab","romosozumab"]},
 "endometriosis": {"name":"Endometriosis","short":"Pelvic pain, diagnosis, and treatment research","category":"Gynecological health","condition":"endometriosis","pubmed":"endometriosis","accent":"coral","examples":["dienogest","elagolix","laparoscopy"]},
 "pmdd": {"name":"Premenstrual dysphoric disorder","short":"Cyclical mood symptoms and treatment research","category":"Mental health","condition":"premenstrual dysphoric disorder","pubmed":"(premenstrual dysphoric disorder OR PMDD)","accent":"lilac","examples":["sertraline","fluoxetine","cognitive behavioral therapy"]},
 "postpartum-depression": {"name":"Postpartum depression","short":"Maternal mental health during and after pregnancy","category":"Maternal health","condition":"postpartum depression","pubmed":"(postpartum depression OR postnatal depression)","accent":"blue","examples":["brexanolone","zuranolone","psychotherapy"]},
 "pcos": {"name":"Polycystic ovary syndrome","short":"Hormonal, metabolic, and reproductive health research","category":"Endocrine health","condition":"polycystic ovary syndrome","pubmed":"(polycystic ovary syndrome OR PCOS)","accent":"mint","examples":["metformin","inositol","lifestyle intervention"]},
 "menopause": {"name":"Perimenopause & menopause","short":"Hormonal transitions, symptoms, and long-term health","category":"Midlife health","condition":"menopause","pubmed":"(perimenopause OR menopause OR menopausal symptoms)","accent":"gold","examples":["estradiol","hormone therapy","vasomotor symptoms"]},
}
class LiteratureItem(BaseModel):
    pmid: str
    title: str
    journal: str | None = None
    published: str | None = None
    authors: list[str] = Field(default_factory=list)
    url: str
class LiteratureResponse(BaseModel):
    topic: str
    retrieved_at: datetime
    items: list[LiteratureItem]
    limitations: str = "Recent PubMed-indexed publications, sorted by publication date. Search results are not a systematic review, evidence-quality assessment, or clinical guidance."

@router.get("/api/topics")
def list_topics():
    return [{"slug":slug, **data} for slug,data in TOPICS.items()]

@router.get("/api/topics/{slug}")
def topic(slug: str):
    if slug not in TOPICS: raise HTTPException(404,"Unknown health topic")
    return {"slug":slug,**TOPICS[slug]}

@router.get("/api/topics/{slug}/literature", response_model=LiteratureResponse)
async def literature(slug: str, limit: int = Query(8,ge=1,le=15)):
    if slug not in TOPICS: raise HTTPException(404,"Unknown health topic")
    base="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    try:
        async with httpx.AsyncClient(timeout=18,headers={"User-Agent":"Mosaic/0.2 research explorer"}) as client:
            r=await client.get(base+"esearch.fcgi",params={"db":"pubmed","term":TOPICS[slug]["pubmed"],"retmode":"json","retmax":limit,"sort":"pub date"})
            r.raise_for_status()
            ids=r.json()["esearchresult"]["idlist"]
            if not ids: return LiteratureResponse(topic=slug,retrieved_at=datetime.now(timezone.utc),items=[])
            r=await client.get(base+"esummary.fcgi",params={"db":"pubmed","id":",".join(ids),"retmode":"json"})
            r.raise_for_status()
            records=r.json()["result"]
            items=[]
            for pmid in ids:
                row=records.get(pmid,{})
                if not re.fullmatch(r"\d+",pmid) or not row.get("title"): continue
                items.append(LiteratureItem(pmid=pmid,title=row["title"],journal=row.get("fulljournalname") or row.get("source"),published=row.get("pubdate"),authors=[a["name"] for a in row.get("authors",[])[:4] if a.get("name")],url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"))
            return LiteratureResponse(topic=slug,retrieved_at=datetime.now(timezone.utc),items=items)
    except (httpx.HTTPError,ValueError,KeyError,TypeError) as exc:
        raise HTTPException(502,"PubMed is temporarily unavailable. Please retry.") from exc

AGE_GROUPS={"18-24":"young adult","25-34":"adult","35-44":"adult","45-54":"middle aged","55-64":"middle aged","65+":"aged"}
DOMAINS={"nutrients":"(vitamins OR minerals OR dietary intake OR nutritional deficiency)","exercise":"(physical activity OR resistance training OR aerobic exercise)","sleep":"(sleep quality OR sleep duration)","prevention":"(preventive health OR screening OR disease prevention)"}
LIFE_STAGES={"":"", "pregnancy":"pregnancy", "postpartum":"postpartum", "perimenopause":"perimenopause", "menopause":"menopause"}

@router.get("/api/wellbeing/literature",response_model=LiteratureResponse)
async def wellbeing_literature(
    age: str = Query("25-34"),
    domain: str = Query("nutrients"),
    life_stage: str = Query(""),
    limit: int = Query(8,ge=1,le=12),
):
    if age not in AGE_GROUPS or domain not in DOMAINS or life_stage not in LIFE_STAGES:
        raise HTTPException(422,"Unknown wellbeing filter")
    # Broad literature discovery only: age and life stage are query terms, not personal medical advice.
    term=f'{DOMAINS[domain]} AND (women OR female) AND "{AGE_GROUPS[age]}"'
    if life_stage: term+=f' AND "{LIFE_STAGES[life_stage]}"'
    base="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    try:
        async with httpx.AsyncClient(timeout=18,headers={"User-Agent":"Mosaic/0.2 research explorer"}) as client:
            r=await client.get(base+"esearch.fcgi",params={"db":"pubmed","term":term,"retmode":"json","retmax":limit,"sort":"pub date"})
            r.raise_for_status()
            ids=r.json()["esearchresult"]["idlist"]
            if not ids: return LiteratureResponse(topic="wellbeing",retrieved_at=datetime.now(timezone.utc),items=[])
            r=await client.get(base+"esummary.fcgi",params={"db":"pubmed","id":",".join(ids),"retmode":"json"})
            r.raise_for_status()
            records=r.json()["result"]
            items=[]
            for pmid in ids:
                row=records.get(pmid,{})
                if not re.fullmatch(r"\d+",pmid) or not row.get("title"): continue
                items.append(LiteratureItem(pmid=pmid,title=row["title"],journal=row.get("fulljournalname") or row.get("source"),published=row.get("pubdate"),authors=[a["name"] for a in row.get("authors",[])[:4] if a.get("name")],url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"))
            return LiteratureResponse(topic="wellbeing",retrieved_at=datetime.now(timezone.utc),items=items,limitations="Keyword-based PubMed discovery by broad age and life-stage terms; articles may not precisely match the selected age bracket. Not personalized advice or a systematic review.")
    except (httpx.HTTPError,ValueError,KeyError,TypeError) as exc:
        raise HTTPException(502,"PubMed is temporarily unavailable. Please retry.") from exc
