"""
Step 9: Add multimodal embeddings to every product.

We re-embed each product's `description` (text) using `voyage-multimodal-3.5`,
which produces 1024-dim vectors in a *shared* text-and-image space. That means
a query image (uploaded by a shopper) can be embedded with the same model and
matched against these document vectors.

Why a *separate* embedding field?
  * `description_embedding` (voyage-4-large) lives in a different vector space
    and stays untouched — text/hybrid/rerank search keep working unchanged.
  * The new `multimodal_embedding` enables image search.

Cost note: ~1k items × ~50 tokens each ≈ negligible at Voyage's $0.12/M tokens.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import voyageai
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MULTIMODAL_MODEL = "voyage-multimodal-3.5"
BATCH_SIZE = 8  # multimodal_embed is heavier per call; keep batches modest

client = MongoClient(os.environ["MONGODB_URI"])
coll = client["workshop"]["products"]
vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

products = list(coll.find({}, {"_id": 1, "name": 1, "description": 1, "category": 1}))
print(f"Found {len(products)} products in workshop.products")

# Build the input we will embed: combine name + category + description so the
# model has a richer textual hook for matching cross-modal queries.
def build_text(p: dict) -> str:
    parts = [
        p.get("name", "").strip(),
        p.get("category", "").strip(),
        (p.get("description") or "").strip(),
    ]
    return " — ".join([x for x in parts if x])


t0 = time.time()
total_done = 0
for i in range(0, len(products), BATCH_SIZE):
    batch = products[i : i + BATCH_SIZE]
    inputs = [[build_text(p)] for p in batch]  # list of [text] inputs
    result = vo.multimodal_embed(
        inputs=inputs,
        model=MULTIMODAL_MODEL,
        input_type="document",
    )
    for p, emb in zip(batch, result.embeddings):
        coll.update_one(
            {"_id": p["_id"]},
            {"$set": {"multimodal_embedding": emb, "multimodal_model": MULTIMODAL_MODEL}},
        )
    total_done += len(batch)
    print(f"  Embedded batch {i // BATCH_SIZE + 1} → {total_done}/{len(products)}")

elapsed = time.time() - t0
with_emb = coll.count_documents({"multimodal_embedding": {"$exists": True}})
print()
print(f"Done in {elapsed:.1f}s. Products with multimodal_embedding: {with_emb}/{len(products)}")
print(f"Embedding model: {MULTIMODAL_MODEL}")
print("Next step: run scripts/10_create_multimodal_index.py")

client.close()
