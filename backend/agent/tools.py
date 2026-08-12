"""Allowlisted tools for the LeafyShop support agent."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable

from pymongo.collection import Collection

SECRET_PATTERNS = re.compile(
  r"(password|api[_-]?key|secret|token|bearer)\s*[:=]",
  re.IGNORECASE,
)

ALLOWED_TOOLS = frozenset({"search_knowledge", "get_product", "save_memory", "recall_memory"})


def _truncate(text: str, limit: int) -> str:
  if len(text) <= limit:
    return text
  return text[: limit - 3] + "..."


def search_knowledge(knowledge_coll: Collection, query: str, *, max_chars: int) -> dict[str, Any]:
  """Keyword search across support knowledge base documents."""
  q = query.strip()[:500]
  if not q:
    return {"matches": [], "count": 0}

  regex = re.compile(re.escape(q), re.IGNORECASE)
  cursor = knowledge_coll.find(
    {
      "$or": [
        {"title": regex},
        {"content": regex},
        {"tags": regex},
      ]
    },
    {"_id": 1, "title": 1, "content": 1, "tags": 1},
  ).limit(5)

  matches = []
  for doc in cursor:
    matches.append(
      {
        "id": str(doc["_id"]),
        "title": doc.get("title", ""),
        "content": _truncate(doc.get("content", ""), 400),
        "tags": doc.get("tags", []),
      }
    )
  return {"matches": matches, "count": len(matches)}


def get_product(products_coll: Collection, product_name: str, *, max_chars: int) -> dict[str, Any]:
  """Look up a product by case-insensitive name match."""
  name = product_name.strip()[:200]
  if not name:
    return {"found": False, "product": None}

  doc = products_coll.find_one(
    {"name": {"$regex": re.escape(name), "$options": "i"}},
    {
      "_id": 0,
      "name": 1,
      "category": 1,
      "description": 1,
      "price": 1,
      "brand": 1,
      "in_stock": 1,
      "tags": 1,
    },
  )
  if not doc:
    return {"found": False, "product": None}

  if doc.get("description"):
    doc["description"] = _truncate(doc["description"], max_chars)
  return {"found": True, "product": doc}


def save_memory(memories_coll: Collection, session_id: str, note: str) -> dict[str, Any]:
  """Persist a short user preference for the session."""
  cleaned = note.strip()[:300]
  if not cleaned:
    return {"saved": False, "reason": "empty note"}
  if SECRET_PATTERNS.search(cleaned):
    return {"saved": False, "reason": "note appears to contain sensitive credentials"}

  doc = {
    "session_id": session_id,
    "note": cleaned,
    "created_at": datetime.now(timezone.utc),
  }
  result = memories_coll.insert_one(doc)
  return {"saved": True, "id": str(result.inserted_id)}


def recall_memory(memories_coll: Collection, session_id: str) -> dict[str, Any]:
  """Return the latest memories for this session."""
  cursor = (
    memories_coll.find({"session_id": session_id}, {"_id": 0, "note": 1, "created_at": 1})
    .sort("created_at", -1)
    .limit(10)
  )
  notes = []
  for doc in cursor:
    created = doc.get("created_at")
    notes.append(
      {
        "note": doc.get("note", ""),
        "created_at": created.isoformat() if created else None,
      }
    )
  return {"memories": notes, "count": len(notes)}


def build_tool_registry(
  *,
  knowledge_coll: Collection,
  products_coll: Collection,
  memories_coll: Collection,
  session_id: str,
  max_result_chars: int,
) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
  """Map allowlisted tool names to callables."""

  def _search(args: dict[str, Any]) -> dict[str, Any]:
    return search_knowledge(knowledge_coll, str(args.get("query", "")), max_chars=max_result_chars)

  def _product(args: dict[str, Any]) -> dict[str, Any]:
    return get_product(products_coll, str(args.get("product_name", "")), max_chars=max_result_chars)

  def _save(args: dict[str, Any]) -> dict[str, Any]:
    return save_memory(memories_coll, session_id, str(args.get("note", "")))

  def _recall(_: dict[str, Any]) -> dict[str, Any]:
    return recall_memory(memories_coll, session_id)

  return {
    "search_knowledge": _search,
    "get_product": _product,
    "save_memory": _save,
    "recall_memory": _recall,
  }
