"""
Solution: create the Vector Search and Atlas Search indexes on workshop.products.

Attendee lab (fill the TODOs yourself):
    python scripts/TO-DO/02_create_indexes.py

Why this index does not vectorize the whole document:
  Creating a Vector Search index does not call Voyage. It builds an HNSW graph
  on the float array already stored at ingest (description_embedding, produced
  from embedding_text: name + tags + description).

  type "vector"  — that one array is the only ANN field.
  type "filter"  — category and price are facts for $vectorSearch.filter,
                   not embeddings. Omit a path = you cannot pre-filter on it.
"""

import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

load_dotenv()

client = MongoClient(os.environ["MONGODB_URI"])
coll = client["workshop"]["products"]

# Vector Search index — for $vectorSearch (semantic search)
vector_model = SearchIndexModel(
    definition={
        "fields": [
            # ANN path only. Voyage already wrote this array at ingest.
            # Creating the index does not embed name, tags, or price.
            {
                "type": "vector",
                "path": "description_embedding",
                "numDimensions": 1024,
                "similarity": "cosine",
            },
            # Not vectors. Metadata so $vectorSearch.filter can pre-filter ANN
            # (department equality, price range). Omit = cannot filter on it.
            {"type": "filter", "path": "category"},  # department sidebar
            {"type": "filter", "path": "price"},  # budget range $gte / $lte
        ]
    },
    name="vector_index",
    type="vectorSearch",
)

# Atlas Search index — for $search (full-text search)
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

print("Creating vector search index...")
coll.create_search_index(vector_model)
print("Creating text search index...")
coll.create_search_index(search_model)
print("Index creation submitted. Poll until READY:")

for idx in coll.list_search_indexes():
    print(f"  {idx.get('name')} — {idx.get('status')} ({idx.get('type')})")

client.close()
