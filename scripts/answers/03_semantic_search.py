"""
Step 3: Run semantic search queries with $vectorSearch.
"""

import os

import voyageai
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ["MONGODB_URI"])
coll = client["workshop"]["products"]
vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])


def vector_search(query: str, limit: int = 5):
    emb = vo.embed([query], model="voyage-4-large", input_type="query")
    query_vector = emb.embeddings[0]

    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "description_embedding",
                "queryVector": query_vector,
                "numCandidates": 100,
                "limit": limit,
            }
        },
        {
            "$project": {
                "_id": 0,
                "name": 1,
                "category": 1,
                "description": 1,
                "price": 1,
                "vectorSearchScore": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    return list(coll.aggregate(pipeline))


queries = [
    "comfortable waterproof shoes for hiking",
    "lightweight running shoes for marathon training",
    "gift ideas for someone who loves cooking",
    "noise cancelling headphones for office work",
]

for query in queries:
    print(f'\n=== "{query}" ===')
    for doc in vector_search(query):
        print(f"  {doc['vectorSearchScore']:.4f}  {doc['name']} (${doc['price']})")

client.close()
