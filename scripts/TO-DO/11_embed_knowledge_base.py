"""
LAB: embed workshop.knowledge_base with Voyage AI.

Fill the ??? below, then from the repo root:

    python scripts/TO-DO/11_embed_knowledge_base.py

Solution: scripts/answers/11_embed_knowledge_base.py

Does not delete articles — only $set content_embedding.
"""

from __future__ import annotations

import os

import voyageai
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ["MONGODB_URI"])
coll = client["workshop"]["knowledge_base"]
vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

# ---------------------------------------------------------------------------
# TODO 1 — Form one string per article
# Vectorise meaning: title + content (customers ask about "returns").
# Do not embed _id.
# ---------------------------------------------------------------------------
docs: list[dict] = list(coll.find({}))
texts: list[str] = []
for doc in docs:
    title = doc["???"]          # TODO 1 — article headline
    content = doc["???"]       # TODO 1 — policy body
    texts.append(f"{title}\n{content}")

if not docs or len(texts) != len(docs):
    raise SystemExit(
        "TODO 1 incomplete: load knowledge_base docs and build one string each."
    )
if any("???" in t for t in texts):
    raise SystemExit("TODO 1: replace ??? with the field names (title and content).")

print(f"Loaded {len(docs)} knowledge_base documents")

# ---------------------------------------------------------------------------
# TODO 2 — Call Voyage AI (same model as products, ingest not query)
# ---------------------------------------------------------------------------
model = "???"                 # TODO 2 — voyage-4-large
input_type = "???"            # TODO 2 — "document"
if "???" in (model, input_type):
    raise SystemExit("TODO 2: fill model and input_type.")
result = vo.embed(texts, model=model, input_type=input_type)

embeddings = result.embeddings
print(f"Generated {len(embeddings)} embeddings of {len(embeddings[0])} dimensions")

# ---------------------------------------------------------------------------
# TODO 3 — $set the vector (do not replace the collection)
# The field name you put here is the index path in 12_create_knowledge_index.py
# ---------------------------------------------------------------------------
for doc, embedding in zip(docs, embeddings):
    coll.update_one(
        {"_id": doc["_id"]},
        {"$set": {"???": embedding}},  # TODO 3 — field name for the array
    )

sample = coll.find_one({"title": {"$regex": "return", "$options": "i"}})
vec = (sample or {}).get("content_embedding")
if not isinstance(vec, list) or len(vec) != 1024:
    raise SystemExit(
        "TODO 3 incomplete: returns article should have content_embedding of length 1024. "
        "Use update_one + $set. The field name must be 'content_embedding'."
    )

print(f"Updated {coll.count_documents({'content_embedding': {'$exists': True}})} docs")
print(f"  Returns article embedding length: {len(vec)}")
client.close()
