"""
LAB: create knowledge_vector_index on workshop.knowledge_base.

    python scripts/TO-DO/12_create_knowledge_index.py

Solution: scripts/answers/12_create_knowledge_index.py

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
# path: the array you stored in 11_embed_knowledge_base.py
# numDimensions: 1024 (voyage-4-large)
# similarity: cosine
# No type "filter" unless you will pass $vectorSearch.filter
# ---------------------------------------------------------------------------
vector_fields: list[dict] = [
    # TODO: one dict, type vector
]


def _require(fields: list[dict]) -> None:
    vectors = [f for f in fields if f.get("type") == "vector"]
    if not vectors:
        raise SystemExit("TODO 1: add type 'vector'.")
    vec = vectors[0]
    if vec.get("path") != "content_embedding":
        raise SystemExit("TODO 1: path must be 'content_embedding'.")
    if vec.get("numDimensions") != 1024:
        raise SystemExit("TODO 1: numDimensions must be 1024.")
    if vec.get("similarity") != "cosine":
        raise SystemExit("TODO 1: similarity must be 'cosine'.")
    if any(f.get("type") == "filter" for f in fields):
        raise SystemExit(
            "v1 has no knowledge filters. Omit type 'filter' unless you will use "
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
