"""
E-Commerce Product Search API — Developer Track Starter.

This is the skeleton version of the app. You'll build each search mode
step by step during the workshop by replacing the TODO sections below.

Run with:  uvicorn app_starter:app --reload
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
import voyageai

load_dotenv()

db_client: MongoClient = None
coll = None
orders_coll = None
vo: voyageai.Client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_client, coll, orders_coll, vo
    db_client = MongoClient(os.environ["MONGODB_URI"])
    db = db_client["workshop"]
    coll = db["products"]
    orders_coll = db["orders"]
    vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
    yield
    db_client.close()


app = FastAPI(title="Product Search API", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="../frontend"), name="static")


def get_query_embedding(text: str) -> list[float]:
    result = vo.embed([text], model="voyage-4-large", input_type="query")
    return result.embeddings[0]


@app.get("/api/search")
def search(
    q: str = Query(..., min_length=1),
    mode: str = Query("hybrid", pattern="^(vector|text|hybrid|rerank)$"),
    category: Optional[str] = None,
    limit: int = Query(12, ge=1, le=50),
):
    if mode == "vector":
        results = vector_search(q, category, limit)
    elif mode == "text":
        results = text_search(q, category, limit)
    elif mode == "rerank":
        results = hybrid_rerank_search(q, category, limit)
    else:
        results = hybrid_search(q, category, limit)
    return {"query": q, "mode": mode, "count": len(results), "results": results}


# ---------------------------------------------------------------------------
# TODO 1: Vector Search (Semantic Search module)
# Replace this function body with the $vectorSearch aggregation pipeline.
# ---------------------------------------------------------------------------
def vector_search(query: str, category: Optional[str], limit: int):
    return []


# ---------------------------------------------------------------------------
# TODO 2: Text Search (Hybrid Search module)
# Replace this function body with the $search aggregation pipeline.
# ---------------------------------------------------------------------------
def text_search(query: str, category: Optional[str], limit: int):
    return []


# ---------------------------------------------------------------------------
# TODO 3: Hybrid Search with RRF (Hybrid Search module)
# Replace this function body with Reciprocal Rank Fusion logic.
# ---------------------------------------------------------------------------
def hybrid_search(query: str, category: Optional[str], limit: int, k: int = 60):
    return []


# ---------------------------------------------------------------------------
# TODO 4: Hybrid + Rerank (Reranking module)
# Replace this function body with the Voyage AI reranking logic.
# ---------------------------------------------------------------------------
def hybrid_rerank_search(query: str, category: Optional[str], limit: int):
    return []


def _serialize(cursor) -> list[dict]:
    results = []
    for doc in cursor:
        doc.pop("_id", None)
        for k, v in doc.items():
            if isinstance(v, float):
                doc[k] = round(v, 4)
        results.append(doc)
    return results


# ---------------------------------------------------------------------------
# Cart & Checkout (pre-built — no changes needed)
# ---------------------------------------------------------------------------
class CartItem(BaseModel):
    name: str
    price: float
    category: str = ""
    brand: str = ""
    quantity: int = 1


class CheckoutRequest(BaseModel):
    user_name: str
    items: list[CartItem]
    search_mode: str = "hybrid"


@app.post("/api/checkout")
def checkout(req: CheckoutRequest):
    if not req.items:
        return {"error": "Cart is empty"}

    total = round(sum(item.price * item.quantity for item in req.items), 2)
    order_doc = {
        "user_name": req.user_name,
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
def get_orders(user_name: str = Query(...)):
    cursor = orders_coll.find({"user_name": user_name}).sort("created_at", -1).limit(20)
    orders = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if "created_at" in doc and isinstance(doc["created_at"], datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        orders.append(doc)
    return {"orders": orders}


@app.get("/", response_class=HTMLResponse)
def root():
    with open("../frontend/index.html") as f:
        return f.read()
