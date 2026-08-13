"""Solution: vector retrieve on workshop.knowledge_base.

Compare-with file for attendees: scripts/answers/retrieval_starter.py
"""

from __future__ import annotations

import os
import time
from typing import Any

import voyageai
from dotenv import load_dotenv
from pymongo.collection import Collection

from .query_log import log_aggregate

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

    t0 = time.perf_counter()
    docs = list(knowledge_coll.aggregate(pipeline))
    log_aggregate(
        "knowledge_base",
        pipeline,
        label=f"Vector search — support articles ({q[:80]})",
        source="vector",
        latency_ms=(time.perf_counter() - t0) * 1000,
        result_count=len(docs),
    )
    return docs
