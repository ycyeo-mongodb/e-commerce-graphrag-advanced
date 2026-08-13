"""
LAB: embed workshop.knowledge_base with Voyage AI.

Fill the TODOs, then from the repo root:

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
# TODO 1 — Load docs and form one string per article
# Vectorise meaning: title + content (customers ask about "returns").
# Do not embed _id.
# ---------------------------------------------------------------------------
docs: list[dict] = []  # TODO: list(coll.find({}))
texts: list[str] = []
# TODO: for each doc, append f"{doc['title']}\n{doc['content']}"

if not docs or len(texts) != len(docs):
    raise SystemExit(
        "TODO 1 incomplete: load knowledge_base docs and build one string each."
    )

print(f"Loaded {len(docs)} knowledge_base documents")

# ---------------------------------------------------------------------------
# TODO 2 — Voyage, same model as products, input_type document
# ---------------------------------------------------------------------------
result = None  # TODO: vo.embed(texts, model="voyage-4-large", input_type="document")
if result is None:
    raise NotImplementedError("TODO 2: embed texts with Voyage AI")

embeddings = result.embeddings
print(f"Generated {len(embeddings)} embeddings of {len(embeddings[0])} dimensions")

# ---------------------------------------------------------------------------
# TODO 3 — $set content_embedding (do not replace the collection)
# ---------------------------------------------------------------------------
updated = 0
for doc, embedding in zip(docs, embeddings):
    # TODO: coll.update_one({"_id": doc["_id"]}, {"$set": {"content_embedding": embedding}})
    if "content_embedding" not in doc:
        pass
    updated += 1

sample = coll.find_one({"title": {"$regex": "return", "$options": "i"}})
vec = (sample or {}).get("content_embedding")
if not isinstance(vec, list) or len(vec) != 1024:
    raise SystemExit(
        "TODO 3 incomplete: returns article should have content_embedding of length 1024. "
        "Use update_one + $set."
    )

print(f"Updated {coll.count_documents({'content_embedding': {'$exists': True}})} docs")
print(f"  Returns article embedding length: {len(vec)}")
client.close()
