"""
LAB 1.3: RAG retrieve — embed the question and run $vectorSearch.

Fill the TODOs in vector_search_knowledge. Smoke test from backend/:

    python -c "from agent.retrieval_starter import smoke; smoke()"

Solution: scripts/answers/retrieval_starter.py
(also backend/agent/retrieval.py — same function, importable by the app)
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

    # TODO 1 — this is a question, not a document
    result = vo.embed([q], model="voyage-4-large", input_type="???")
    query_vector = result.embeddings[0]

    pipeline: list[dict[str, Any]] = [
        {
            "$vectorSearch": {
                "index": "???",   # knowledge_vector_index from Aftersales Knowledge
                "path": "???",    # field you $set the article embedding array on
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

    stage = pipeline[0].get("$vectorSearch") or {}
    if stage.get("index") in {None, "", "???"} or stage.get("path") in {None, "", "???"}:
        raise SystemExit(
            "TODO 2: set $vectorSearch index (the knowledge index name) and "
            "path (the field you stored the article embedding array on)."
        )

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
