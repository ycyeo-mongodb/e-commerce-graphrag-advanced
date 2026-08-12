"""
Step 5 (Bonus): Rerank hybrid search results with Voyage AI rerank-2.5.
"""

import os

import voyageai
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ["MONGODB_URI"])
coll = client["workshop"]["products"]
vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])


def hybrid_search(query: str, limit: int = 30, k: int = 60):
    """Retrieve candidates using hybrid search (vector + text + RRF)."""
    query_vector = vo.embed([query], model="voyage-4-large", input_type="query").embeddings[0]

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

    text_results = list(coll.aggregate([
        {
            "$search": {
                "index": "text_search_index",
                "text": {"query": query, "path": ["name", "description"]},
            }
        },
        {"$addFields": {"ts_score": {"$meta": "searchScore"}}},
        {"$project": {"description_embedding": 0}},
        {"$limit": 50},
    ]))

    rrf: dict[str, float] = {}
    doc_map: dict[str, dict] = {}

    for rank, doc in enumerate(vector_results):
        doc_id = str(doc["_id"])
        rrf[doc_id] = rrf.get(doc_id, 0) + 1 / (k + rank + 1)
        doc_map[doc_id] = doc

    for rank, doc in enumerate(text_results):
        doc_id = str(doc["_id"])
        rrf[doc_id] = rrf.get(doc_id, 0) + 1 / (k + rank + 1)
        doc_map[doc_id] = doc

    sorted_ids = sorted(rrf, key=lambda x: rrf[x], reverse=True)[:limit]
    return [doc_map[did] for did in sorted_ids]


def rerank_results(query: str, candidates: list[dict], top_k: int = 10):
    """Rerank candidate products using Voyage AI rerank-2.5."""
    descriptions = [doc.get("description", doc.get("name", "")) for doc in candidates]

    reranked = vo.rerank(
        query=query,
        documents=descriptions,
        model="rerank-2.5",
        top_k=top_k,
    )

    results = []
    for r in reranked.results:
        doc = candidates[r.index]
        doc["rerank_score"] = round(r.relevance_score, 4)
        results.append(doc)
    return results


# Compare with and without reranking
test_queries = [
    "lightweight breathable shoes for summer running",
    "comfortable shoes for standing all day at work",
    "birthday gift for a tech enthusiast",
    "waterproof jacket for rainy city commutes",
]

for query in test_queries:
    candidates = hybrid_search(query, limit=20)
    reranked = rerank_results(query, candidates, top_k=5)

    print(f'\n=== "{query}" ===')
    print("  Hybrid top-3:")
    for doc in candidates[:3]:
        print(f"    - {doc['name']}")
    print("  Reranked top-3:")
    for doc in reranked[:3]:
        print(f"    - [{doc['rerank_score']:.4f}] {doc['name']}")

client.close()
