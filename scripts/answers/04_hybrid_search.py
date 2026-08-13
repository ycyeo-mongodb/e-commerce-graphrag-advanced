"""
Step 4: Hybrid search combining $vectorSearch + $search with Reciprocal Rank Fusion.
"""

import os

import voyageai
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ["MONGODB_URI"])
coll = client["workshop"]["products"]
vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])


def hybrid_search(query: str, limit: int = 10, k: int = 60):
    """Hybrid search combining vector + text search with RRF."""

    emb = vo.embed([query], model="voyage-4-large", input_type="query")
    query_vector = emb.embeddings[0]

    # Vector search
    vector_results = list(coll.aggregate([
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "description_embedding",
                "queryVector": query_vector,
                "numCandidates": 150,
                "limit": 50,
            }
        },
        {"$addFields": {"vs_score": {"$meta": "vectorSearchScore"}}},
        {"$project": {"description_embedding": 0}},
    ]))

    # Text search
    text_results = list(coll.aggregate([
        {
            "$search": {
                "index": "text_search_index",
                "text": {
                    "query": query,
                    "path": ["name", "description"],
                },
            }
        },
        {"$addFields": {"ts_score": {"$meta": "searchScore"}}},
        {"$project": {"description_embedding": 0}},
        {"$limit": 50},
    ]))

    # Reciprocal Rank Fusion
    rrf_scores: dict[str, float] = {}
    doc_map: dict[str, dict] = {}

    for rank, doc in enumerate(vector_results):
        doc_id = str(doc["_id"])
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank + 1)
        doc_map[doc_id] = doc

    for rank, doc in enumerate(text_results):
        doc_id = str(doc["_id"])
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank + 1)
        doc_map[doc_id] = doc

    sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)

    results = []
    for doc_id in sorted_ids[:limit]:
        doc = doc_map[doc_id]
        doc["rrf_score"] = round(rrf_scores[doc_id], 6)
        results.append(doc)
    return results


# Test queries
print("=== 'Nike running shoes' (keyword strength) ===")
for r in hybrid_search("Nike running shoes", limit=5):
    print(f"  {r['rrf_score']:.6f}  {r['name']}")

print()
print("=== 'something warm and cozy for winter' (vector strength) ===")
for r in hybrid_search("something warm and cozy for winter", limit=5):
    print(f"  {r['rrf_score']:.6f}  {r['name']}")

print()
print("=== 'durable leather laptop bag' (hybrid strength) ===")
for r in hybrid_search("durable leather laptop bag", limit=5):
    print(f"  {r['rrf_score']:.6f}  {r['name']}")

client.close()
