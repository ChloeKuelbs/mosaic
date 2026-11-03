"""Six curated research topics and live PubMed publication metadata."""
from datetime import datetime, timezone
import re
import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()
TOPICS = {
 "bone-health": dict(name="Bone health & osteoporosis",short="Bone density, fracture prevention, and treatment research.",condition="postmenopausal osteoporosis",pubmed="(osteoporosis OR bone density) AND (women OR postmenopausal)",accent="sage",examples=["alendronate","denosumab","romosozumab"],number="01"),
 "endometriosis": dict(name="Endometriosis",short="Pelvic pain, diagnosis, and emerging treatment research.",condition="endometriosis",pubmed="endometriosis",accent="coral",examples=["dienogest","elagolix","laparoscopy"],number="02"),
 "pmdd": dict(name="Premenstrual dysphoric disorder",short="Cyclical mood symptoms, diagnosis, and treatment research.",condition="premenstrual dysphoric disorder",pubmed="(premenstrual dysphoric disorder OR PMDD)",accent="lilac",examples=["sertraline","fluoxetine","cognitive behavioral therapy"],number="03"),
 "postpartum-depression": dict(name="Postpartum depression",short="Maternal mental health during and after pregnancy.",condition="postpartum depression",pubmed="(postpartum depression OR postnatal depression)",accent="blue",examples=["brexanolone","zuranolone","psychotherapy"],number="04"),
 "pcos": dict(name="Polycystic ovary syndrome",short="Hormonal, metabolic, and reproductive health research.",condition="polycystic ovary syndrome",pubmed="(polycystic ovary syndrome OR PCOS)",accent="mint",examples=["metformin","inositol","lifestyle intervention"],number="05"),
 "menopause": dict(name="Perimenopause & menopause",short="Hormonal transitions, symptoms, and long-term health.",condition="menopause",pubmed="(perimenopause OR menopause OR menopausal symptoms)",accent="gold",examples=["estradiol","menopausal hormone therapy","vasomotor symptoms"],number="06"),
}

@router.get("/api/topics")
def topics():
 return [{"slug": slug, **topic} for slug,topic in TOPICS.items()]

@router.get("/api/topics/{slug}")
def topic(slug: str):
 if slug not in TOPICS: raise HTTPException(404,"Unknown health topic")
 return {"slug":slug, **TOPICS[slug]}

@router.get("/api/topics/{slug}/literature")
async def literature(slug: str, limit: int=Query(8,ge=1,le=15)):
 if slug not in TOPICS: raise HTTPException(404,"Unknown health topic")
 base="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
 try:
  async with httpx.AsyncClient(timeout=18,headers={"User-Agent":"Mosaic educational research explorer"}) as client:
   r=await client.get(base+"esearch.fcgi",params={"db":"pubmed","term":TOPICS[slug]["pubmed"],"retmode":"json","retmax":limit,"sort":"pub date"})
   r.raise_for_status()
   ids=r.json()["esearchresult"]["idlist"]
   items=[]
   if ids:
    r=await client.get(base+"esummary.fcgi",params={"db":"pubmed","id":",".join(ids),"retmode":"json"})
    r.raise_for_status()
    data=r.json()["result"]
    for pmid in ids:
     if not re.fullmatch(r"\d+",pmid): continue
     row=data.get(pmid,{})
     if not row.get("title"): continue
     items.append({"pmid":pmid,"title":row["title"],"journal":row.get("fulljournalname") or row.get("source"),"published":row.get("pubdate"),"authors":[a["name"] for a in row.get("authors",[])[:4] if a.get("name")],"url":f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"})
   return {"topic":slug,"retrieved_at":datetime.now(timezone.utc).isoformat(),"items":items,"limitations":"Recent PubMed-indexed records sorted by publication date; not a systematic review or quality ranking. Abstracts and findings are not evaluated."}
 except (httpx.HTTPError,ValueError,KeyError,TypeError) as exc:
  raise HTTPException(502,"PubMed literature is temporarily unavailable.") from exc
