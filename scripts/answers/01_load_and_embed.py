"""
Solution: load the product catalog and generate embeddings with Voyage AI.
Inserts all products with embeddings into MongoDB Atlas.

Vectorise meaning; filter on facts: one embedding_text string (name + tags +
description) → one Voyage vector on description_embedding. Category and price
are not in that string — they are Vector Search filter fields.

Attendee lab (fill the TODOs yourself):
    python scripts/TO-DO/01_load_and_embed.py
"""

import json
import os
from pathlib import Path

import voyageai
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ["MONGODB_URI"])
coll = client["workshop"]["products"]
vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

# Load the product catalog
with open(Path(__file__).resolve().parents[2] / "backend" / "data" / "products.json") as f:
    products = json.load(f)

print(f"Loaded {len(products)} products")
print(f"Categories: {sorted(set(p['category'] for p in products))}")

def embedding_text(product: dict) -> str:
    """Vectorise meaning; filter on facts.

    One string → one Voyage vector. Include natural-language fields shoppers
    actually type (name, tags, description). Leave facts out (price, category,
    ids, stock) — those belong on the Vector Search index as filter paths.
    """
    name = (product.get("name") or "").strip()
    subcategory = (product.get("subcategory") or "").strip()
    tags = ", ".join(str(t) for t in (product.get("tags") or []) if t)
    highlights = ", ".join(str(h) for h in (product.get("spec_highlights") or []) if h)
    description = (product.get("description") or "").strip()
    parts = [p for p in (name, subcategory, tags, highlights, description) if p]
    return ". ".join(parts)


texts = [embedding_text(p) for p in products]
batch_size = 128
all_embeddings: list[list[float]] = []

for i in range(0, len(texts), batch_size):
    batch = texts[i : i + batch_size]
    result = vo.embed(batch, model="voyage-4-large", input_type="document")
    all_embeddings.extend(result.embeddings)
    print(f"  Embedded batch {i // batch_size + 1} ({len(all_embeddings)}/{len(texts)})")

for product, text, embedding in zip(products, texts, all_embeddings):
    product["embedding_text"] = text
    product["description_embedding"] = embedding

print(f"Generated {len(all_embeddings)} embeddings of {len(all_embeddings[0])} dimensions")

# Insert into MongoDB
coll.delete_many({})
result = coll.insert_many(products)
print(f"Inserted {len(result.inserted_ids)} products into workshop.products")

# Verify
print(f"\nTotal products: {coll.count_documents({})}")
pipeline = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}]
for doc in coll.aggregate(pipeline):
    print(f"  {doc['_id']}: {doc['count']}")

client.close()
