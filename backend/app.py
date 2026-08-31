"""
E-Commerce Product Search API.
Supports vector search, text search, hybrid search, hybrid + rerank, and
multimodal image search (upload a photo and find matching catalog items).
Includes mock cart & checkout for workshop interactivity.
"""

import io
import json
import logging
import os
import re
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from PIL import Image
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
import voyageai

# Repo-root `.env` is the workshop file. Optional `backend/.env` still works.
BACKEND_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = (BACKEND_DIR.parent / "frontend").resolve()
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

from agent import SupportAgent
from agent.agent import build_agent_trace
from agent.query_log import get_cluster_label, get_recent_queries, set_active_session
from agent.tools import persist_conversation_turn
from catalog_browse import browse_products

# Workshop wiring — UI → API → lab file
#   Page load / sidebar     GET  /api/products        backend/catalog_browse.py
#   Search bar              GET  /api/search          app.py hybrid_search (not a lab)
#   Green chat bubble       POST /api/support/chat    agent/tools.py + retrieval_starter.py
#   Checkout / orders       POST /api/checkout, GET /api/orders   app.py (data for Part 2)
#   Live MongoDB overlay    GET  /api/queries         agent/query_log.py
# Solutions: scripts/answers/catalog_browse.py, scripts/answers/tools.py,
#            scripts/answers/retrieval_starter.py

logger = logging.getLogger("leafyshop")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

db_client: MongoClient = None
coll = None
orders_coll = None
knowledge_coll = None
memories_coll = None
user_profiles_coll = None
conversations_coll = None
vo: voyageai.Client = None
_watcher_stop = threading.Event()
_watcher_thread: Optional[threading.Thread] = None


def _enrich_product(doc_id, name: str, price: float) -> None:
    """Call Bedrock + Voyage to fill in description/category/tags/embedding for a bare product."""
    bedrock_url = os.environ.get("BEDROCK_API_URL", "").rstrip("/")
    if not bedrock_url:
        logger.warning("BEDROCK_API_URL not set — skipping enrichment for %s", doc_id)
        return

    prompt = (
        "You are a product catalog AI. Given a product name and price, "
        "generate detailed e-commerce listing information.\n\n"
        f"Product Name: {name}\nPrice: ${price}\n\n"
        "Respond with ONLY valid JSON:\n"
        '{"description":"2-3 sentence description","category":"Top > Sub",'
        '"tags":["t1","t2","t3","t4","t5"],"brand":"BrandName"}'
    )
    resp = requests.post(
        f"{bedrock_url}/genai_workshop",
        json={"action": "answer", "question": prompt, "context": "", "max_tokens": 500, "temperature": 0.3},
        timeout=45,
    )
    resp.raise_for_status()
    answer = (resp.json() or {}).get("answer", "")
    start, end = answer.find("{"), answer.rfind("}") + 1
    details = json.loads(answer[start:end] if start >= 0 and end > start else answer)

    embedding = vo.embed([details["description"]], model="voyage-4-large", input_type="document").embeddings[0]
    coll.update_one(
        {"_id": doc_id},
        {"$set": {
            "description": details["description"],
            "category": details.get("category", "Uncategorized"),
            "tags": details.get("tags", []),
            "brand": details.get("brand", "Generic"),
            "description_embedding": embedding,
            "status": "active",
            "enriched_by": "claude-4.5-haiku",
            "enriched_at": datetime.now(timezone.utc),
        }},
    )
    logger.info("Enrichment complete: %s (%s)", name, doc_id)


def _catalog_watcher_loop() -> None:
    """Watch for new bare-product inserts and trigger enrichment in-process.

    Runs on its own thread because PyMongo's change stream cursor is sync/blocking.
    """
    pipeline = [{"$match": {"operationType": "insert", "fullDocument.status": "pending_enrichment"}}]
    while not _watcher_stop.is_set():
        try:
            with coll.watch(pipeline, max_await_time_ms=5000) as stream:
                logger.info("Catalog watcher attached to change stream")
                while not _watcher_stop.is_set():
                    change = stream.try_next()
                    if change is None:
                        continue
                    doc = change["fullDocument"]
                    logger.info("New product detected: %s ($%s)", doc.get("name"), doc.get("price"))
                    try:
                        _enrich_product(doc["_id"], doc["name"], doc.get("price", 0))
                    except Exception as e:
                        logger.exception("Enrichment failed: %s", e)
        except Exception as e:
            if _watcher_stop.is_set():
                break
            logger.exception("Catalog watcher error, retrying in 5s: %s", e)
            _watcher_stop.wait(5)
    logger.info("Catalog watcher stopped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_client, coll, orders_coll, knowledge_coll, memories_coll, user_profiles_coll, conversations_coll, vo, _watcher_thread
    db_client = MongoClient(os.environ["MONGODB_URI"])
    db = db_client["workshop"]
    coll = db["products"]
    orders_coll = db["orders"]
    knowledge_coll = db["knowledge_base"]
    memories_coll = db["memories"]
    user_profiles_coll = db["user_profiles"]
    conversations_coll = db["conversations"]
    vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

    if os.environ.get("ENABLE_CATALOG_WATCHER", "0") == "1" and os.environ.get("BEDROCK_API_URL"):
        _watcher_stop.clear()
        _watcher_thread = threading.Thread(target=_catalog_watcher_loop, name="catalog-watcher", daemon=True)
        _watcher_thread.start()
        logger.info("Catalog watcher thread started")

    yield

    _watcher_stop.set()
    if _watcher_thread:
        _watcher_thread.join(timeout=10)
    db_client.close()


app = FastAPI(title="LeafyShop API — GraphRAG Advanced", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost(:\d+)?|.*\.cloudfront\.net|.*\.awsapprunner\.com)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


def get_query_embedding(text: str) -> list[float]:
    result = vo.embed([text], model="voyage-4-large", input_type="query")
    return result.embeddings[0]


# ─────────────────────────────────────────────────────────────────
# Search configuration constants — surfaced so the UI can show them.
# ─────────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "voyage-4-large"
MULTIMODAL_MODEL = "voyage-multimodal-3.5"
RERANK_MODEL = "rerank-2.5"
RRF_K = 60                  # reciprocal-rank-fusion constant
HYBRID_CANDIDATES = 50      # docs pulled from each retriever before fusion
RERANK_CANDIDATES = 30      # docs sent into the reranker after RRF
FUZZY_MAX_EDITS = 1         # Atlas Search fuzzy: short tokens must not edit into "on"/"can"
FUZZY_PREFIX_LEN = 2        # first N chars must match exactly
FUZZY_MIN_TERM_LEN = 4      # do not fuzzy "on", "at", "can"
TEXT_SEARCH_PATHS = ["name", "description"]
# Natural-language glue. lucene.standard does not strip these, so "I can … at home"
# otherwise ranks Can-opener / Home Decor / Roll-on over GPUs.
_TEXT_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "from", "i", "i'm", "im", "can", "could", "would", "should", "want",
    "need", "get", "me", "my", "we", "you", "that", "this", "it", "is", "are",
    "be", "as", "by", "about", "into", "over", "do", "does", "did", "just",
    "some", "any", "also", "able", "use", "using", "used",
})
# Catalog names say RTX / GeForce, not "GPU". Expand type words so $search can hit them.
_TEXT_SYNONYMS = {
    "gpu": ["graphics", "rtx", "geforce", "radeon"],
    "gpus": ["graphics", "rtx", "geforce", "radeon"],
}
POPULARITY_WEIGHT = 0.2     # mild tiebreaker only (intent=none). Equal weight lets high-review noise beat GPUs.
POPULARITY_INTENT_RE = r"\b(popular|popularity|bestseller|best[- ]?selling|top[- ]?rated|highest[- ]?rated|best[- ]?rated|highly[- ]?rated|most[- ]?loved|trending|favorite|favourite)\b"
REVIEWS_INTENT_RE = r"\b(most[- ]?reviewed|highly[- ]?reviewed|most[- ]?reviews|reviewed)\b"
POPULARITY_INTENT_WEIGHT = 4.0  # bump popularity retriever further when the query asks for it
MAX_IMAGE_BYTES = 10 * 1024 * 1024   # 10 MB hard limit on uploads
IMAGE_RESIZE_MAX = 1024              # cap longest side; multimodal models tokenize per pixel


@app.get("/api/search")
def search(
    q: str = Query(..., min_length=1),
    category: Optional[str] = None,
    limit: int = Query(12, ge=1, le=50),
    explain: bool = Query(False, description="Include per-stage diagnostics for the UI modal."),
):
    """Product search — workshop demo always uses hybrid RRF (vector + text fusion).
    Search bar only. Not a lab — product indexes come from scripts/TO-DO/02_create_indexes.py.
    """
    results, debug = hybrid_search(q, category, limit, explain=explain)

    payload = {"query": q, "mode": "hybrid", "count": len(results), "results": results}
    if explain:
        payload["explain"] = debug
    return payload


@app.get("/api/products")
def list_products(
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    sort: str = Query("popular", pattern="^(popular|newest|rating|price_asc|price_desc)$"),
    limit: int = Query(12, ge=1, le=60),
):
    """Home page + sidebar. Lab: backend/catalog_browse.py (find + category filter)."""
    results = browse_products(
        coll,
        category=category,
        subcategory=subcategory,
        sort=sort,
        limit=limit,
    )
    return {
        "mode": "browse",
        "sort": sort,
        "category": category,
        "subcategory": subcategory,
        "count": len(results),
        "results": results,
    }


# ─────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────

def _build_vector_pipeline(query_vector: list[float], category: Optional[str], limit: int) -> list[dict]:
    """Build the $vectorSearch pipeline. Returned as a plain list[dict] so we can
    both execute it and surface it in the explain payload."""
    vs_stage: dict = {
        "$vectorSearch": {
            "index": "vector_index",
            "path": "description_embedding",
            "queryVector": query_vector,
            "numCandidates": max(100, limit * 10),
            "limit": limit,
        }
    }
    if category:
        vs_stage["$vectorSearch"]["filter"] = {"category": category}
    return [
        vs_stage,
        {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
        {"$project": {"description_embedding": 0}},
    ]


def _lexical_terms(query: str) -> list[str]:
    """Keep content tokens for $search. Drop glue so BM25 does not rank 'home' decor."""
    raw = [t for t in re.split(r"[^\w+]+", query.lower()) if t]
    kept = [t for t in raw if t not in _TEXT_STOPWORDS and len(t) > 1]
    base = kept or raw
    expanded: list[str] = []
    seen: set[str] = set()
    for t in base:
        for piece in [t, *_TEXT_SYNONYMS.get(t, [])]:
            if piece not in seen:
                seen.add(piece)
                expanded.append(piece)
    return expanded


def _build_text_pipeline(query: str, category: Optional[str], limit: int) -> list[dict]:
    """Lexical $search: exact on content terms, fuzzy only on longer tokens.

    Product type words like GPU often live in tags, not the title. Until
    text_search_index maps tags, expand GPU → RTX / GeForce so name search hits.
    Fuzzy is limited to terms with length >= FUZZY_MIN_TERM_LEN so maxEdits cannot
    turn 'on'/'can' into Roll-on / Can-opener.
    """
    terms = _lexical_terms(query)
    joined = " ".join(terms) if terms else query
    fuzzy_terms = [t for t in terms if len(t) >= FUZZY_MIN_TERM_LEN]
    should: list[dict] = [
        {
            "text": {
                "query": joined,
                "path": "name",
                "score": {"boost": {"value": 3}},
            }
        },
        {
            "text": {
                "query": joined,
                "path": "description",
            }
        },
    ]
    if fuzzy_terms:
        should.append({
            "text": {
                "query": " ".join(fuzzy_terms),
                "path": TEXT_SEARCH_PATHS,
                "fuzzy": {"maxEdits": FUZZY_MAX_EDITS, "prefixLength": FUZZY_PREFIX_LEN},
            }
        })
    compound: dict = {
        "should": should,
        "minimumShouldMatch": 1,
    }
    if category:
        compound["filter"] = [{"text": {"query": category, "path": "category"}}]

    return [
        {"$search": {"index": "text_search_index", "compound": compound}},
        {"$addFields": {"score": {"$meta": "searchScore"}}},
        {"$project": {"description_embedding": 0}},
        {"$limit": limit},
    ]


def _doc_key(doc: dict, fallback_index: int) -> str:
    """Stable per-document key used by the RRF fusion table."""
    return str(doc.get("id", fallback_index))


def _popularity_score(doc: dict) -> float:
    """Composite popularity prior:  (rating/5)  *  log10(1 + reviews_count).
    Range ≈ 0 .. 4. Higher = more popular AND well-rated."""
    import math
    rating = doc.get("rating") or 0
    reviews = doc.get("reviews_count") or 0
    return (rating / 5.0) * math.log10(1 + reviews)


def _reviews_score(doc: dict) -> float:
    """Pure reviews-count prior (raw count). Used when the query says 'most reviewed'.
    Higher = more reviews. Rating is ignored."""
    return float(doc.get("reviews_count") or 0)


def _build_popularity_ranking(doc_map: dict[str, dict], by: str = "popularity") -> list[str]:
    """Rank candidate doc ids by the chosen prior, descending.
    `by` ∈ {"popularity", "reviews"}.

    Operates over the *union* of vector + text candidates so the prior only
    re-orders among already-relevant docs (never injects unrelated ones).
    """
    score_fn = _reviews_score if by == "reviews" else _popularity_score
    return sorted(doc_map.keys(), key=lambda did: score_fn(doc_map[did]), reverse=True)


def _detect_intent(query: str) -> str:
    """Return 'reviews', 'popularity', or 'none' based on query wording.
    'reviews' takes precedence because 'most reviewed' is a more specific signal."""
    import re
    if re.search(REVIEWS_INTENT_RE, query, flags=re.IGNORECASE):
        return "reviews"
    if re.search(POPULARITY_INTENT_RE, query, flags=re.IGNORECASE):
        return "popularity"
    return "none"


def _intent_match_details(query: str) -> dict:
    """Return what regex matched (for the MongoDB Query Inspector modal)."""
    import re
    rev = re.search(REVIEWS_INTENT_RE, query, flags=re.IGNORECASE)
    pop = re.search(POPULARITY_INTENT_RE, query, flags=re.IGNORECASE)
    return {
        "reviews_pattern": REVIEWS_INTENT_RE,
        "reviews_match": rev.group(0) if rev else None,
        "popularity_pattern": POPULARITY_INTENT_RE,
        "popularity_match": pop.group(0) if pop else None,
    }


def _prior_query_spec(intent: str, category: Optional[str], sort_spec: list, limit: int) -> dict:
    """Serializable description of Retriever C's MongoDB query, suitable for
    pretty-printing in the Query Inspector modal and pasting into the shell."""
    filter_expr: dict = {"category": category} if category else {}
    projection = {"description_embedding": 0, "multimodal_embedding": 0}
    sort_obj = {field: direction for field, direction in sort_spec}
    return {
        "operation": "find().sort().limit()",
        "collection": "workshop.products",
        "filter": filter_expr,
        "projection": projection,
        "sort": sort_obj,
        "limit": limit,
        # Equivalent shell command — copy-paste into mongosh / Compass shell
        "shell": (
            "db.products.find(\n"
            f"  {json.dumps(filter_expr)},\n"
            f"  {json.dumps(projection)}\n"
            f").sort({json.dumps(sort_obj)}).limit({limit})"
        ),
        # Equivalent Python pymongo call
        "pymongo": (
            "coll.find(\n"
            f"    {filter_expr!r},\n"
            f"    {projection!r}\n"
            f").sort({sort_spec!r}).limit({limit})"
        ),
        "intent": intent,
    }


# ─────────────────────────────────────────────────────────────────
# Search modes
# ─────────────────────────────────────────────────────────────────

def vector_search(query: str, category: Optional[str], limit: int, explain: bool = False):
    query_vector = get_query_embedding(query)
    pipeline = _build_vector_pipeline(query_vector, category, limit)
    results = _serialize(coll.aggregate(pipeline))
    debug = None
    if explain:
        debug = {
            "stages": [
                {
                    "name": "Embed query",
                    "detail": f"Voyage AI {EMBEDDING_MODEL} → {len(query_vector)}-dim vector",
                    "embedding_preview": [round(v, 4) for v in query_vector[:8]],
                    "embedding_dims": len(query_vector),
                },
                {
                    "name": "$vectorSearch",
                    "detail": "Cosine similarity over description_embedding",
                    "pipeline": pipeline,
                    "results": _summarise(results, "similarity"),
                },
            ],
        }
    return results, debug


def text_search(query: str, category: Optional[str], limit: int, explain: bool = False):
    pipeline = _build_text_pipeline(query, category, limit)
    results = _serialize(coll.aggregate(pipeline))
    debug = None
    if explain:
        debug = {
            "stages": [
                {
                    "name": "$search (compound: exact + fuzzy)",
                    "detail": (
                        f"Atlas Search BM25-like text scoring on name + description, "
                        f"with fuzzy maxEdits={FUZZY_MAX_EDITS}, prefixLength={FUZZY_PREFIX_LEN}"
                    ),
                    "fuzzy": {"maxEdits": FUZZY_MAX_EDITS, "prefixLength": FUZZY_PREFIX_LEN},
                    "pipeline": pipeline,
                    "results": _summarise(results, "text score"),
                },
            ],
        }
    return results, debug


def hybrid_search(query: str, category: Optional[str], limit: int, k: int = RRF_K, explain: bool = False):
    """Reciprocal Rank Fusion of vector + text + popularity rankings.
    score(doc) = Σ_retriever  weight_r * 1 / (k + rank_in_retriever + 1)

    Popularity is computed over the *union* of vector + text candidates only,
    so it re-orders relevant docs but never injects unrelated ones.
    The popularity retriever's weight auto-boosts when the query contains
    popularity-intent terms (e.g. "most popular", "top rated").
    """
    query_vector = get_query_embedding(query)
    vector_pipeline = _build_vector_pipeline(query_vector, category, HYBRID_CANDIDATES)
    text_pipeline = _build_text_pipeline(query, category, HYBRID_CANDIDATES)

    vector_results = _serialize(coll.aggregate(vector_pipeline))
    text_results = _serialize(coll.aggregate(text_pipeline))

    # Detect intent — the prior we apply (and how we pick the global pool) depends on it.
    #   intent="reviews"     -> "most reviewed" : sort global pool by reviews_count, prior = raw reviews
    #   intent="popularity"  -> "most popular"  : sort global pool by (rating, reviews), prior = (rating/5)*log(reviews)
    #   intent="none"        -> normal hybrid, mild popularity prior as tiebreaker
    intent = _detect_intent(query)
    if intent != "none":
        sort_spec = (
            [("reviews_count", -1), ("rating", -1)]
            if intent == "reviews"
            else [("rating", -1), ("reviews_count", -1)]
        )
        prior_query_spec = _prior_query_spec(intent, category, sort_spec, HYBRID_CANDIDATES)
        filter_expr = prior_query_spec["filter"]
        top_rated_cursor = coll.find(
            filter_expr, {"description_embedding": 0, "multimodal_embedding": 0}
        ).sort(sort_spec).limit(HYBRID_CANDIDATES)
        top_rated_results = _serialize(top_rated_cursor)
    else:
        sort_spec = [("rating", -1), ("reviews_count", -1)]  # for prior re-ranking only
        prior_query_spec = _prior_query_spec("none", category, sort_spec, 0)
        prior_query_spec["note"] = "intent=none — no global pool injection. Prior re-ranks the existing vector+text candidate pool only."
        top_rated_results = []

    # Snapshot retriever scores BEFORE fusion mutates `score` to the RRF value.
    vector_summary = _summarise(vector_results, "similarity", top=10) if explain else None
    text_summary = _summarise(text_results, "text score", top=10) if explain else None

    rrf: dict[str, float] = {}
    contrib: dict[str, dict] = {}
    doc_map: dict[str, dict] = {}

    for rank, doc in enumerate(vector_results):
        did = _doc_key(doc, rank)
        c = 1 / (k + rank + 1)
        rrf[did] = rrf.get(did, 0) + c
        contrib.setdefault(did, {})["vector"] = {"rank": rank + 1, "score": doc.get("score"), "contrib": round(c, 6)}
        doc_map[did] = doc

    for rank, doc in enumerate(text_results):
        did = _doc_key(doc, rank)
        c = 1 / (k + rank + 1)
        rrf[did] = rrf.get(did, 0) + c
        contrib.setdefault(did, {})["text"] = {"rank": rank + 1, "score": doc.get("score"), "contrib": round(c, 6)}
        doc_map[did] = doc

    # When intent is explicit, also pour globally-top docs into the
    # candidate pool (they enter at vector/text rank == 0 contribution only).
    # They'll get re-ranked normally by the prior retriever below.
    for doc in top_rated_results:
        did = _doc_key(doc, len(doc_map))
        if did not in doc_map:
            doc_map[did] = doc
            rrf.setdefault(did, 0)

    # Prior retriever (Retriever C) — ranks the candidate pool by the chosen prior.
    pop_weight = POPULARITY_INTENT_WEIGHT if intent != "none" else POPULARITY_WEIGHT
    rank_by = "reviews" if intent == "reviews" else "popularity"
    popularity_ranking = _build_popularity_ranking(doc_map, by=rank_by)
    score_fn = _reviews_score if rank_by == "reviews" else _popularity_score
    for rank, did in enumerate(popularity_ranking):
        c = pop_weight * (1 / (k + rank + 1))
        rrf[did] = rrf.get(did, 0) + c
        contrib.setdefault(did, {})["popularity"] = {
            "rank": rank + 1,
            "rating": doc_map[did].get("rating"),
            "reviews_count": doc_map[did].get("reviews_count"),
            "prior": rank_by,
            "score": round(score_fn(doc_map[did]), 4),
            "contrib": round(c, 6),
        }

    sorted_ids = sorted(rrf, key=lambda x: rrf[x], reverse=True)[:limit]
    results: list[dict] = []
    for did in sorted_ids:
        doc = doc_map[did]
        doc["score"] = round(rrf[did], 6)
        results.append(doc)

    debug = None
    if explain:
        # Build a flat fusion table: top docs with their per-retriever contributions.
        fusion_rows = []
        for did in sorted_ids:
            d = doc_map[did]
            row = {
                "id": d.get("id"),
                "name": d.get("name"),
                "vector": contrib.get(did, {}).get("vector"),
                "text": contrib.get(did, {}).get("text"),
                "popularity": contrib.get(did, {}).get("popularity"),
                "rrf_score": round(rrf[did], 6),
            }
            fusion_rows.append(row)

        pop_summary = [
            {
                "rank": i + 1,
                "id": doc_map[did].get("id"),
                "name": doc_map[did].get("name"),
                "rating": doc_map[did].get("rating"),
                "reviews_count": doc_map[did].get("reviews_count"),
                "prior_score": round(score_fn(doc_map[did]), 4),
            }
            for i, did in enumerate(popularity_ranking[:10])
        ]

        debug = {
            "stages": [
                {
                    "name": "Embed query",
                    "detail": f"Voyage AI {EMBEDDING_MODEL} → {len(query_vector)}-dim vector",
                    "embedding_preview": [round(v, 4) for v in query_vector[:8]],
                    "embedding_dims": len(query_vector),
                },
                {
                    "name": "Retriever A — $vectorSearch",
                    "detail": f"Top {HYBRID_CANDIDATES} candidates by cosine similarity",
                    "pipeline": vector_pipeline,
                    "results": vector_summary,
                },
                {
                    "name": "Retriever B — $search (exact + fuzzy)",
                    "detail": (
                        f"Top {HYBRID_CANDIDATES} candidates from Atlas Search on "
                        f"name + description; stopwords stripped; fuzzy only on terms "
                        f"≥{FUZZY_MIN_TERM_LEN} chars (maxEdits={FUZZY_MAX_EDITS})"
                    ),
                    "fuzzy": {"maxEdits": FUZZY_MAX_EDITS, "prefixLength": FUZZY_PREFIX_LEN},
                    "pipeline": text_pipeline,
                    "results": text_summary,
                },
                {
                    "name": "Retriever C — Prior (popularity / reviews)",
                    "detail": (
                        ("Prior = reviews_count (raw). " if rank_by == "reviews"
                         else "Prior = (rating/5) * log10(1 + reviews_count). ")
                        + f"Weight = {pop_weight}. "
                        + f"Intent detected: '{intent}'."
                    ),
                    "intent": intent,
                    "intent_match": _intent_match_details(query),
                    "prior_kind": rank_by,
                    "weight": pop_weight,
                    "query_spec": prior_query_spec,
                    "results": pop_summary,
                },
                {
                    "name": "Fusion — Reciprocal Rank Fusion (vector + text + popularity)",
                    "detail": f"score(doc) = Σ weight_r / (k + rank_r + 1) with k = {k}",
                    "rrf_k": k,
                    "popularity_weight": pop_weight,
                    "fusion_rows": fusion_rows,
                },
            ],
        }
    return results, debug


def hybrid_rerank_search(query: str, category: Optional[str], limit: int, explain: bool = False):
    candidates, hybrid_debug = hybrid_search(query, category, RERANK_CANDIDATES, explain=explain)
    if not candidates:
        return candidates, hybrid_debug

    descriptions = [doc.get("description", doc.get("name", "")) for doc in candidates]
    reranked = vo.rerank(query=query, documents=descriptions, model=RERANK_MODEL, top_k=limit)

    # Capture the pre-rerank order so the UI can show the reordering.
    rrf_order = [
        {"id": d.get("id"), "name": d.get("name"), "rrf_score": d.get("score")}
        for d in candidates
    ]

    results: list[dict] = []
    rerank_rows = []
    for new_rank, r in enumerate(reranked.results):
        doc = candidates[r.index]
        prev_rank = r.index + 1
        doc["score"] = round(r.relevance_score, 4)
        results.append(doc)
        rerank_rows.append({
            "id": doc.get("id"),
            "name": doc.get("name"),
            "rrf_rank": prev_rank,
            "rerank_rank": new_rank + 1,
            "rrf_score": rrf_order[r.index]["rrf_score"],
            "rerank_score": round(r.relevance_score, 4),
            "moved": prev_rank - (new_rank + 1),
        })

    debug = None
    if explain:
        debug = {
            "stages": (hybrid_debug.get("stages", []) if hybrid_debug else []) + [
                {
                    "name": f"Rerank — Voyage AI {RERANK_MODEL}",
                    "detail": (
                        f"Top {RERANK_CANDIDATES} RRF candidates → cross-encoder relevance "
                        "scores (query × document jointly), highest-relevance shown first"
                    ),
                    "rerank_model": RERANK_MODEL,
                    "rerank_rows": rerank_rows,
                }
            ],
        }
    return results, debug


def _summarise(results: list[dict], score_label: str, top: int = 10) -> list[dict]:
    """Trim per-stage results for the UI: id, name, category, score only."""
    out = []
    for i, doc in enumerate(results[:top]):
        out.append({
            "rank": i + 1,
            "id": doc.get("id"),
            "name": doc.get("name"),
            "category": doc.get("category"),
            "score": doc.get("score"),
            "score_label": score_label,
        })
    return out


def _serialize(cursor) -> list[dict]:
    results = []
    for doc in cursor:
        doc.pop("_id", None)
        for k, v in doc.items():
            if isinstance(v, float):
                doc[k] = round(v, 4)
        results.append(doc)
    return results


# ─────────────────────────────────────────────────────────────────
# Multimodal image search
#
# Shopper uploads a photo (e.g. a model wearing a denim jacket) and optionally
# adds a text refinement ("similar but in red"). We embed [text?, image] with
# voyage-multimodal-3.5 — a single transformer backbone that puts text and
# images in the same vector space — then $vectorSearch on the catalog's
# `multimodal_embedding` field, which was built with the same model.
# ─────────────────────────────────────────────────────────────────

def _load_and_resize_image(raw: bytes) -> Image.Image:
    """Open + downscale the upload so we don't pay for unnecessary tokens
    (every 560 pixels is one token for voyage-multimodal-3.5)."""
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not decode image: {e}")
    # Drop alpha + EXIF orientation handling
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    longest = max(img.size)
    if longest > IMAGE_RESIZE_MAX:
        scale = IMAGE_RESIZE_MAX / longest
        new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    return img


def _multimodal_search_pipeline(query_vector: list[float], category: Optional[str], limit: int) -> list[dict]:
    vs_stage: dict = {
        "$vectorSearch": {
            "index": "multimodal_index",
            "path": "multimodal_embedding",
            "queryVector": query_vector,
            "numCandidates": max(150, limit * 12),
            "limit": limit,
        }
    }
    if category:
        vs_stage["$vectorSearch"]["filter"] = {"category": category}
    return [
        vs_stage,
        {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
        {"$project": {"description_embedding": 0, "multimodal_embedding": 0}},
    ]


@app.post("/api/search/image")
async def search_by_image(
    image: UploadFile = File(..., description="Product photo, outfit shot, or any reference image"),
    q: Optional[str] = Form(None, description="Optional text refinement, e.g. 'similar but in black'"),
    category: Optional[str] = Form(None),
    limit: int = Form(12),
    explain: bool = Form(False),
):
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 50")

    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty upload.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large. Limit is {MAX_IMAGE_BYTES // (1024*1024)}MB.",
        )

    pil_image = _load_and_resize_image(raw)
    refinement = (q or "").strip()

    # Voyage multimodal accepts a list of inputs; each input is an interleaved
    # sequence of strings and PIL Images. With one input, we get one vector.
    if refinement:
        # Phrase the text as an instruction so the model understands the
        # refinement applies to the image.
        composed_prompt = f"Find products matching this photo. Additional preference: {refinement}"
        sequence = [composed_prompt, pil_image]
    else:
        sequence = ["Find products matching this photo.", pil_image]

    try:
        result = vo.multimodal_embed(
            inputs=[sequence],
            model=MULTIMODAL_MODEL,
            input_type="query",
        )
    except Exception as e:
        logger.exception("multimodal embed failed")
        raise HTTPException(status_code=502, detail=f"Embedding failed: {e}")

    query_vector = result.embeddings[0]
    pipeline = _multimodal_search_pipeline(query_vector, category, limit)
    results = _serialize(coll.aggregate(pipeline))

    payload: dict = {
        "mode": "multimodal",
        "query_text": refinement,
        "image_filename": image.filename,
        "image_size_bytes": len(raw),
        "image_resized_to": list(pil_image.size),
        "model": MULTIMODAL_MODEL,
        "count": len(results),
        "results": results,
    }
    if explain:
        payload["explain"] = {
            "stages": [
                {
                    "name": f"Embed [text?, image] with {MULTIMODAL_MODEL}",
                    "detail": (
                        "Single transformer backbone produces a 1024-dim vector for the "
                        "interleaved query (instruction text + uploaded image). The same "
                        "model embedded every product description, so they share a vector space."
                    ),
                    "embedding_preview": [round(v, 4) for v in query_vector[:8]],
                    "embedding_dims": len(query_vector),
                    "input_pieces": (
                        ["text", "image"] if refinement else ["image"]
                    ),
                    "image_size": list(pil_image.size),
                    "total_tokens": getattr(result, "total_tokens", None),
                },
                {
                    "name": "$vectorSearch on multimodal_index",
                    "detail": (
                        f"Cosine similarity over multimodal_embedding (1024-dim, {MULTIMODAL_MODEL}); "
                        f"top {limit} of {pipeline[0]['$vectorSearch']['numCandidates']} candidates"
                    ),
                    "pipeline": pipeline,
                    "results": _summarise(results, "similarity"),
                },
            ],
        }
    return payload


class CartItem(BaseModel):
    name: str
    price: float
    category: str = ""
    brand: str = ""
    quantity: int = 1


class CheckoutRequest(BaseModel):
    user_name: str = ""
    user_id: str = ""
    items: list[CartItem]
    search_mode: str = "hybrid"


@app.post("/api/checkout")
def checkout(req: CheckoutRequest):
    if not req.items:
        return {"error": "Cart is empty"}

    user_id = (req.user_id or "").strip()
    user_name = (req.user_name or "").strip()
    if user_id and user_profiles_coll is not None:
        profile = user_profiles_coll.find_one({"user_id": user_id}, {"display_name": 1})
        if profile:
            user_name = profile.get("display_name") or user_name
    if not user_name:
        user_name = "LeafyShop User"

    total = round(sum(item.price * item.quantity for item in req.items), 2)
    order_doc = {
        "user_id": user_id or None,
        "user_name": user_name,
        "items": [item.model_dump() for item in req.items],
        "total": total,
        "item_count": sum(item.quantity for item in req.items),
        "search_mode_used": req.search_mode,
        "created_at": datetime.now(timezone.utc),
    }
    result = orders_coll.insert_one(order_doc)
    order_doc["_id"] = str(result.inserted_id)
    return {"order_id": order_doc["_id"], "total": total, "item_count": order_doc["item_count"]}


@app.get("/api/orders")
def get_orders(user_name: str = Query(None), user_id: str = Query(None)):
    if user_id:
        query = {"user_id": user_id}
    elif user_name:
        query = {"user_name": user_name}
    else:
        return {"orders": []}

    cursor = orders_coll.find(query).sort("created_at", -1).limit(20)
    orders = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if "created_at" in doc and isinstance(doc["created_at"], datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        orders.append(doc)
    return {"orders": orders}


class UserInterestRequest(BaseModel):
    user_id: str
    product_name: str
    category: str = ""
    brand: str = ""


@app.get("/api/user/profile")
def get_user_profile_api(user_id: str = Query(...)):
    if user_profiles_coll is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    doc = user_profiles_coll.find_one({"user_id": user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail=f"User {user_id!r} not found")

    member_since = doc.get("member_since")
    if member_since and isinstance(member_since, datetime):
        doc["member_since"] = member_since.isoformat()
    for item in doc.get("recently_viewed") or []:
        viewed_at = item.get("viewed_at")
        if viewed_at and isinstance(viewed_at, datetime):
            item["viewed_at"] = viewed_at.isoformat()
    return {"profile": doc}


@app.post("/api/user/interest")
def record_user_interest(req: UserInterestRequest):
    """Track product interest for the demo shopper profile."""
    if user_profiles_coll is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    user_id = req.user_id.strip()
    product_name = req.product_name.strip()
    if not user_id or not product_name:
        return {"recorded": False, "reason": "user_id and product_name required"}

    entry = {
        "product_name": product_name,
        "category": req.category.strip(),
        "brand": req.brand.strip(),
        "viewed_at": datetime.now(timezone.utc),
    }
    user_profiles_coll.update_one(
        {"user_id": user_id},
        {
            "$push": {
                "recently_viewed": {
                    "$each": [entry],
                    "$position": 0,
                    "$slice": 20,
                }
            },
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
        upsert=False,
    )
    return {"recorded": True, "product_name": product_name}


class SellerProduct(BaseModel):
    name: str
    price: float


@app.post("/api/seller/add-product")
def seller_add_product(product: SellerProduct):
    doc = {
        "name": product.name,
        "price": round(product.price, 2),
        "status": "pending_enrichment",
        "created_at": datetime.now(timezone.utc),
    }
    result = coll.insert_one(doc)
    return {
        "id": str(result.inserted_id),
        "name": doc["name"],
        "price": doc["price"],
        "status": doc["status"],
    }


@app.get("/api/seller/recent")
def seller_recent(limit: int = Query(10, ge=1, le=30)):
    from bson import ObjectId
    cursor = coll.find().sort("_id", -1).limit(limit)
    items = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        doc["has_embedding"] = "description_embedding" in doc
        doc.pop("description_embedding", None)
        if "created_at" in doc and isinstance(doc["created_at"], datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        if "enriched_at" in doc and isinstance(doc["enriched_at"], datetime):
            doc["enriched_at"] = doc["enriched_at"].isoformat()
        items.append(doc)
    return {"products": items}


@app.get("/healthz")
def healthz():
    """App Runner health check."""
    return {"status": "ok"}


@app.get("/api/queries")
def list_queries(limit: int = Query(50, ge=1, le=100), session_id: str | None = None):
    """Live MongoDB query log for the inspector overlay."""
    queries = get_recent_queries(limit=limit, session_id=session_id)
    return {
        "db": "workshop",
        "cluster": get_cluster_label(),
        "count": len(queries),
        "queries": queries,
    }


class SupportChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    user_id: str | None = None


@app.post("/api/support/chat")
def support_chat(req: SupportChatRequest):
    """LeafyShop product support agent.

    Lab: backend/agent/retrieval_starter.py ($vectorSearch) and backend/agent/tools.py
    (catalog + memory tools). Solutions in scripts/answers/.
    """
    if knowledge_coll is None or memories_coll is None or coll is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    session_id = req.session_id or str(uuid.uuid4())
    user_id = (req.user_id or "").strip() or None
    set_active_session(session_id)

    started = datetime.now(timezone.utc)
    agent = SupportAgent(
        knowledge_coll=knowledge_coll,
        products_coll=coll,
        memories_coll=memories_coll,
        user_profiles_coll=user_profiles_coll,
        orders_coll=orders_coll,
        conversations_coll=conversations_coll,
        session_id=session_id,
        user_id=user_id,
    )
    try:
        result = agent.run(req.message)
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    reply = result.get("answer", "")
    if not isinstance(reply, str):
        reply = json.dumps(reply, default=str)
    latency_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
    agent_trace = build_agent_trace(result.get("trace", []), latency_ms=latency_ms)

    if user_id and conversations_coll is not None:
        try:
            persist_conversation_turn(
                conversations_coll,
                user_id=user_id,
                session_id=session_id,
                role="user",
                content=req.message,
            )
            if reply:
                persist_conversation_turn(
                    conversations_coll,
                    user_id=user_id,
                    session_id=session_id,
                    role="assistant",
                    content=reply,
                    trace=result.get("trace"),
                )
        except Exception:
            logger.exception("Failed to persist conversation turn")

    tool_calls = [
        {
            "tool": t.get("tool"),
            "summary": t.get("summary"),
            "step": t.get("step"),
        }
        for t in result.get("trace", [])
        if t.get("kind") in {"tool_call", "tool_result"}
    ]
    return {
        "reply": reply,
        "session_id": session_id,
        "user_id": user_id,
        "trace": result.get("trace", []),
        "agent_trace": agent_trace,
        "tool_calls": tool_calls,
        "cart_items": result.get("cart_items") or [],
    }


def _serve_index() -> str:
    html = (FRONTEND_DIR / "index.html").read_text()
    bedrock_url = os.environ.get("BEDROCK_API_URL", "").rstrip("/")
    inject = f'<script>window.BEDROCK_API_URL = "{bedrock_url}";</script>'
    return html.replace("</head>", f"{inject}</head>", 1)


def _index_response() -> HTMLResponse:
    return HTMLResponse(
        content=_serve_index(),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


@app.get("/", response_class=HTMLResponse)
def root():
    return _index_response()


# CloudFront may rewrite `/` to `/index.html` when DefaultRootObject is set on the
# distribution — serve the same SPA bundle for both paths so prefix-routed deployments work.
@app.get("/index.html", response_class=HTMLResponse, include_in_schema=False)
def index_html():
    return _index_response()
