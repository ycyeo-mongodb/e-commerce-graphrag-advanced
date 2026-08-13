"""
LAB: create an Atlas Vector Search index on workshop.products.

Fill the TODOs below, then from the repo root:

    python scripts/TO-DO/02_create_indexes.py

Solution (instructor / if you get stuck): scripts/answers/02_create_indexes.py

A Vector Search index lists only the fields Atlas may use at query time.
It does NOT vectorize the whole document.

  - type "vector"  — ONE embedding path: the field name that stores the
                     float array you wrote at ingest. Creating this index
                     does not call Voyage.
  - type "filter"  — facts for $vectorSearch.filter (the shop's department
                     sidebar and budget). Not embeddings.

Fields you omit (name, tags, …) stay on the document but are not in this index.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

load_dotenv()

client = MongoClient(os.environ["MONGODB_URI"])
coll = client["workshop"]["products"]

# Set True if Getting Started already created vector_index and you want to rebuild it.
RECREATE = False

# ---------------------------------------------------------------------------
# TODO 1 — Vector field
# path must be the field name you stored the embedding array on in 01_load_and_embed.py
# numDimensions must match voyage-4-large (1024)
# similarity: "cosine" (Voyage retrieval)
# ---------------------------------------------------------------------------
# TODO 2 — Filter fields
# Add one {"type": "filter", "path": "..."} per metadata field you will pass
# to $vectorSearch.filter. The LeafyShop sidebar filters by category.
# Price is a numeric range ($gte / $lte). Do not add name or description.
# ---------------------------------------------------------------------------
vector_fields: list[dict] = [
    # TODO: append the vector field dict, then the filter field dicts
]


def _require_vector_definition(fields: list[dict]) -> None:
    vectors = [f for f in fields if f.get("type") == "vector"]
    filters = [f for f in fields if f.get("type") == "filter"]
    filter_paths = {f.get("path") for f in filters}

    if not vectors:
        raise SystemExit("TODO 1 incomplete: add a field with type 'vector'.")
    vec = vectors[0]
    if vec.get("path") != "description_embedding":
        raise SystemExit("TODO 1: path must be 'description_embedding' (the field you stored).")
    if vec.get("numDimensions") != 1024:
        raise SystemExit("TODO 1: numDimensions must be 1024 for voyage-4-large.")
    if vec.get("similarity") != "cosine":
        raise SystemExit("TODO 1: similarity must be 'cosine'.")

    if "category" not in filter_paths:
        raise SystemExit(
            "TODO 2 incomplete: add a filter on 'category' — the department sidebar "
            "uses $vectorSearch.filter. Without this path, Atlas cannot pre-filter ANN."
        )
    if "price" not in filter_paths:
        raise SystemExit(
            "TODO 2 incomplete: add a filter on 'price' — numeric range filters "
            "($lte / $gte) only work on paths declared as type 'filter'."
        )
    if filter_paths & {"name", "title", "description"}:
        raise SystemExit(
            "TODO 2: do not index name/title/description as vector filters. "
            "Those are content (already in the embedding). Keyword search uses "
            "the Atlas Search index below, not $vectorSearch.filter."
        )


_require_vector_definition(vector_fields)

vector_model = SearchIndexModel(
    definition={"fields": vector_fields},
    name="vector_index",
    type="vectorSearch",
)

# Atlas Search (keyword / fuzzy on name + description) — provided.
# This is a different index type. Filter fields on the vector index do not
# replace it.
search_model = SearchIndexModel(
    definition={
        "mappings": {
            "dynamic": False,
            "fields": {
                "name": {"type": "string", "analyzer": "lucene.standard"},
                "description": {"type": "string", "analyzer": "lucene.standard"},
                "category": {"type": "stringFacet"},
                "brand": {"type": "stringFacet"},
            },
        }
    },
    name="text_search_index",
    type="search",
)

existing = {idx.get("name"): idx.get("status") for idx in coll.list_search_indexes()}

if RECREATE and "vector_index" in existing:
    print("Dropping existing vector_index so you can recreate it...")
    coll.drop_search_index("vector_index")
    existing.pop("vector_index", None)

if "vector_index" in existing:
    print(f"vector_index already exists ({existing['vector_index']}).")
    print("  Set RECREATE = True at the top of this file to drop and rebuild it.")
else:
    print("Creating vector search index...")
    coll.create_search_index(vector_model)

if "text_search_index" not in existing:
    print("Creating text search index...")
    coll.create_search_index(search_model)
else:
    print(f"text_search_index already exists ({existing['text_search_index']}).")

print("Index creation submitted. Poll until READY:")
for idx in coll.list_search_indexes():
    print(f"  {idx.get('name')} — {idx.get('status')} ({idx.get('type')})")

client.close()
