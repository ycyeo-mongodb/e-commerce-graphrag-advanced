"""
Solution: the TO-DO lab with the ??? in vector_fields filled. Same file.

    python scripts/TO-DO/12_create_knowledge_index.py

Do not reuse the product vector_index. No category/price filters on articles.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

load_dotenv()

client = MongoClient(os.environ["MONGODB_URI"])
coll = client["workshop"]["knowledge_base"]

RECREATE = False

# ---------------------------------------------------------------------------
# TODO 1 — Vector field only
# path:           the array you stored in 11_embed_knowledge_base.py
# numDimensions:  voyage-4-large (length of that array)
# similarity:     Voyage retrieval
# No type "filter" — support articles have no category/price sidebar.
# ---------------------------------------------------------------------------
vector_fields: list[dict] = [
    {
        "type": "vector",
        "path": "content_embedding",
        "numDimensions": 1024,
        "similarity": "cosine",
    },
]


def _require(fields: list[dict]) -> None:
    if any(v in ("???", 0) for f in fields for v in f.values()):
        raise SystemExit("TODO 1: fill the ??? in vector_fields before running.")

    vectors = [f for f in fields if f.get("type") == "vector"]
    if not vectors:
        raise SystemExit("TODO 1: type must be 'vector'.")
    vec = vectors[0]
    if vec.get("path") != "content_embedding":
        raise SystemExit("TODO 1: path must be 'content_embedding' (the field you $set in 11).")
    if vec.get("numDimensions") != 1024:
        raise SystemExit("TODO 1: numDimensions must be 1024.")
    if vec.get("similarity") != "cosine":
        raise SystemExit("TODO 1: similarity must be 'cosine'.")
    if any(f.get("type") == "filter" for f in fields):
        raise SystemExit(
            "No knowledge filters. Omit type 'filter' unless you will use "
            "$vectorSearch.filter on that path."
        )


_require(vector_fields)

model = SearchIndexModel(
    definition={"fields": vector_fields},
    name="knowledge_vector_index",
    type="vectorSearch",
)

existing = {idx.get("name"): idx.get("status") for idx in coll.list_search_indexes()}

if RECREATE and "knowledge_vector_index" in existing:
    print("Dropping existing knowledge_vector_index...")
    coll.drop_search_index("knowledge_vector_index")
    existing.pop("knowledge_vector_index", None)

if "knowledge_vector_index" in existing:
    print(f"knowledge_vector_index already exists ({existing['knowledge_vector_index']}).")
    print("  Set RECREATE = True to drop and rebuild it.")
else:
    print("Creating knowledge_vector_index...")
    coll.create_search_index(model)

print("Poll until READY:")
for idx in coll.list_search_indexes():
    print(f"  {idx.get('name')} — {idx.get('status')} ({idx.get('type')})")

client.close()
