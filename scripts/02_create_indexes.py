"""
Step 2: Create the Vector Search and Atlas Search indexes.
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
            {
                "type": "vector",
                "path": "description_embedding",
                "numDimensions": 1024,
                "similarity": "cosine",
            },
            {"type": "filter", "path": "category"},
            {"type": "filter", "path": "price"},
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
