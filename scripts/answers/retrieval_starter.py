"""
Solution: embed the question and run $vectorSearch on workshop.knowledge_base.

Attendee lab: backend/agent/retrieval_starter.py

    python scripts/answers/retrieval_starter.py

The three blanks:
  - Voyage input_type = "query" (this is a question, not a document)
  - index = "knowledge_vector_index"
  - path = "content_embedding"
"""

from __future__ import annotations

import os
from typing import Any

import voyageai
from dotenv import load_dotenv
from pymongo.collection import Collection

load_dotenv()


def vector_search_knowledge(
    knowledge_coll: Collection,
    query: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []

    vo = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
    result = vo.embed([q], model="voyage-4-large", input_type="query")
    query_vector = result.embeddings[0]

    pipeline: list[dict[str, Any]] = [
        {
            "$vectorSearch": {
                "index": "knowledge_vector_index",
                "path": "content_embedding",
                "queryVector": query_vector,
                "numCandidates": 50,
                "limit": limit,
            }
        },
        {
            "$project": {
                "title": 1,
                "content": 1,
                "tags": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    return list(knowledge_coll.aggregate(pipeline))


def smoke() -> None:
    from pymongo import MongoClient

    client = MongoClient(os.environ["MONGODB_URI"])
    coll = client["workshop"]["knowledge_base"]
    hits = vector_search_knowledge(
        coll,
        "Can I send something back if I don't like it?",
        limit=5,
    )
    print(f"{len(hits)} hits")
    for h in hits:
        print(f"  {h.get('score', 0):.3f}  {h.get('title')}")
    client.close()


if __name__ == "__main__":
    smoke()
