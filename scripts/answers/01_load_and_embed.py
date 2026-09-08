"""
Solution: the TO-DO lab with the three TODOs filled. Same file, same loop.

    python scripts/TO-DO/01_load_and_embed.py

This script loads backend/data/products.json, builds one text string per
product (name + tags + description — not price or category), embeds that
string, and inserts into workshop.products. Running it replaces that collection.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import voyageai
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "backend" / "data" / "products.json"

client = MongoClient(os.environ["MONGODB_URI"])
coll = client["workshop"]["products"]
vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

with open(CATALOG_PATH) as f:
    products = json.load(f)

print(f"Loaded {len(products)} products")
print(f"Categories: {sorted(set(p['category'] for p in products))}")

# ---------------------------------------------------------------------------
# TODO 1 — Build the embedding string (not a MongoDB query)
# Voyage encodes one STRING per product. Concatenate meaning-bearing fields.
# Join tags into text. Leave price and category out — those are filters (lab 00).
# $vectorSearch still returns the whole document, so you do not embed price
# in order to show price later.
# ---------------------------------------------------------------------------
texts: list[str] = []
for p in products:
    name = p["name"]
    tags = ", ".join(p.get("tags", []) or [])
    description = p["description"]
    embedding_text = f"{name}. {tags}. {description}"
    texts.append(embedding_text)

if len(texts) != len(products):
    raise SystemExit(
        "TODO 1 incomplete: texts must have one string per product "
        f"(got {len(texts)}, expected {len(products)})."
    )

# ---------------------------------------------------------------------------
# TODO 2 — Call Voyage AI
# Model:      voyage-4-large
# input_type: "document"   (this is ingest; use "query" only at search time)
# Batch size 128 stays under typical rate limits.
# Each result.embeddings[i] is a 1,024-float vector.
# ---------------------------------------------------------------------------
batch_size = 128
all_embeddings: list[list[float]] = []

for i in range(0, len(texts), batch_size):
    batch = texts[i : i + batch_size]
    result = vo.embed(batch, model="voyage-4-large", input_type="document")
    all_embeddings.extend(result.embeddings)
    print(f"  Embedded batch {i // batch_size + 1} ({len(all_embeddings)}/{len(texts)})")

if len(all_embeddings) != len(products):
    raise SystemExit(
        "TODO 2 incomplete: expected one embedding per product "
        f"(got {len(all_embeddings)}, expected {len(products)})."
    )

print(f"Generated {len(all_embeddings)} embeddings of {len(all_embeddings[0])} dimensions")

# ---------------------------------------------------------------------------
# TODO 3 — Store the vector on the MongoDB document
# The Atlas Vector Search index path is description_embedding — the field
# name on the document must match.
# ---------------------------------------------------------------------------
for product, embedding in zip(products, all_embeddings):
    product["description_embedding"] = embedding

# Insert into MongoDB (replaces the collection)
coll.delete_many({})
result = coll.insert_many(products)
print(f"Inserted {len(result.inserted_ids)} products into workshop.products")

print(f"\nTotal products: {coll.count_documents({})}")
sample = coll.find_one({"name": {"$regex": "RTX 5090", "$options": "i"}})
if sample and isinstance(sample.get("description_embedding"), list):
    print(f"  RTX 5090 embedding length: {len(sample['description_embedding'])}")
else:
    print("  Warning: RTX 5090 is missing description_embedding — check TODO 3.")

pipeline = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}]
for doc in coll.aggregate(pipeline):
    print(f"  {doc['_id']}: {doc['count']}")

client.close()
