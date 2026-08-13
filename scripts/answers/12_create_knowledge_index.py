"""
Solution: Vector Search index on workshop.knowledge_base (content_embedding).

Attendee lab: python scripts/TO-DO/12_create_knowledge_index.py
"""

import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

load_dotenv()

client = MongoClient(os.environ["MONGODB_URI"])
coll = client["workshop"]["knowledge_base"]

model = SearchIndexModel(
    definition={
        "fields": [
            {
                "type": "vector",
                "path": "content_embedding",
                "numDimensions": 1024,
                "similarity": "cosine",
            }
        ]
    },
    name="knowledge_vector_index",
    type="vectorSearch",
)

print("Creating knowledge_vector_index...")
coll.create_search_index(model)
print("Poll until READY:")
for idx in coll.list_search_indexes():
    print(f"  {idx.get('name')} — {idx.get('status')} ({idx.get('type')})")

client.close()
