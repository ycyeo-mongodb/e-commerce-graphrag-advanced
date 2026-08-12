"""
Step 10: Create the Atlas Vector Search index for multimodal embeddings.

This is a NEW index, in addition to the existing vector_index — it sits on the
`multimodal_embedding` field and is queried by the /api/search/image endpoint
when shoppers upload a photo.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

INDEX_NAME = "multimodal_index"

client = MongoClient(os.environ["MONGODB_URI"])
coll = client["workshop"]["products"]

existing = {idx["name"] for idx in coll.list_search_indexes()}
if INDEX_NAME in existing:
    print(f"Index {INDEX_NAME!r} already exists. Skipping creation.")
else:
    model = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "multimodal_embedding",
                    "numDimensions": 1024,
                    "similarity": "cosine",
                },
                {"type": "filter", "path": "category"},
                {"type": "filter", "path": "price"},
            ]
        },
        name=INDEX_NAME,
        type="vectorSearch",
    )
    coll.create_search_index(model)
    print(f"Submitted {INDEX_NAME!r} for build.")

# Poll briefly so the operator can see it transition to READY.
deadline = time.time() + 180
while time.time() < deadline:
    indexes = {idx["name"]: idx for idx in coll.list_search_indexes()}
    info = indexes.get(INDEX_NAME)
    status = info.get("status") if info else "missing"
    queryable = info.get("queryable") if info else False
    print(f"  status: {status}, queryable: {queryable}")
    if queryable:
        break
    time.sleep(10)

client.close()
