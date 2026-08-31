"""Allowlisted tools for the LeafyShop support agent.

Part 2 lab: fill the MongoDB bodies (save_memory, recall_memory,
summarize_purchase_history, plus profile / orders). Solution: scripts/answers/tools.py

search_knowledge is already wired to retrieval_starter.py — fill that file in the RAG lab.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable

from pymongo.collection import Collection

from .query_log import log_aggregate, log_find, log_insert_one

SECRET_PATTERNS = re.compile(
  r"(password|api[_-]?key|secret|token|bearer)\s*[:=]",
  re.IGNORECASE,
)

ALLOWED_TOOLS = frozenset({
  "search_knowledge",
  "get_product",
  "compare_products",
  "add_to_cart",
  "get_user_profile",
  "get_purchase_history",
  "summarize_purchase_history",
  "save_memory",
  "recall_memory",
})

MEMORY_SCOPE_SESSION = "session"
MEMORY_SCOPE_LONG_TERM = "long_term"
PRODUCT_TEXT_INDEX = "text_search_index"
CATALOG_SEARCH_LIMIT = 5

_PRICE_DESC = re.compile(
  r"\b(most expensive|expensive|highest|priciest|premium|flagship)\b",
  re.IGNORECASE,
)
_PRICE_ASC = re.compile(
  r"\b(cheapest|least expensive|lowest|affordable|budget|inexpensive)\b",
  re.IGNORECASE,
)


def _price_sort_direction(raw: str) -> int | None:
  if _PRICE_DESC.search(raw):
    return -1
  if _PRICE_ASC.search(raw):
    return 1
  return None


def enrich_product_query(tool_arg: str, user_message: str) -> str:
  """Keep 'most expensive' from the shopper if the model stripped it."""
  arg = (tool_arg or "").strip()
  msg = (user_message or "").strip()
  if _price_sort_direction(msg) and not _price_sort_direction(arg):
    return msg[:200]
  return arg or msg


def _truncate(text: str, limit: int) -> str:
  if len(text) <= limit:
    return text
  return text[: limit - 3] + "..."


def search_knowledge(knowledge_coll: Collection, query: str, *, max_chars: int) -> dict[str, Any]:
  """$vectorSearch on workshop.knowledge_base — fill retrieval_starter.py in the RAG lab."""
  q = query.strip()[:500]
  if not q:
    return {"matches": [], "count": 0, "mode": "vector"}

  from .retrieval_starter import vector_search_knowledge

  hits = vector_search_knowledge(knowledge_coll, q, limit=5)
  matches = []
  for doc in hits:
    matches.append(
      {
        "id": str(doc.get("_id", "")),
        "title": doc.get("title", ""),
        "content": _truncate(doc.get("content", ""), max_chars),
        "tags": doc.get("tags", []),
        "score": doc.get("score"),
      }
    )
  return {"matches": matches, "count": len(matches), "mode": "vector"}


def get_product(products_coll: Collection, product_name: str, *, max_chars: int) -> dict[str, Any]:
  """TODO: Atlas $search on workshop.products (text_search_index). Always return price.

  Solution: scripts/answers/tools.py
  """
  raw = product_name.strip()[:200]
  if not raw:
    return {"found": False, "product": None, "matches": [], "count": 0, "mode": "todo"}
  # TODO: $search on PRODUCT_TEXT_INDEX, path name + description, limit CATALOG_SEARCH_LIMIT.
  # TODO: if the shopper asked "most expensive" / "cheapest", sort by the price field.
  return {"found": False, "product": None, "matches": [], "count": 0, "mode": "todo"}


def compare_products(
  products_coll: Collection,
  product_a: str,
  product_b: str,
  *,
  max_chars: int,
) -> dict[str, Any]:
  """Looks up two products via get_product — fill get_product first."""
  left = get_product(products_coll, product_a, max_chars=max_chars)
  right = get_product(products_coll, product_b, max_chars=max_chars)
  a = left.get("product")
  b = right.get("product")
  missing = [
    name
    for name, hit in ((product_a, left), (product_b, right))
    if not hit.get("found")
  ]
  if not a or not b:
    return {
      "compared": False,
      "product_a": a,
      "product_b": b,
      "differences": [],
      "missing": missing,
    }
  return {
    "compared": True,
    "product_a": a,
    "product_b": b,
    "differences": [],
    "missing": [],
  }


def add_to_cart(products_coll: Collection, product_name: str, *, max_chars: int) -> dict[str, Any]:
  """Looks up a product via get_product — fill get_product first."""
  lookup = get_product(products_coll, product_name, max_chars=max_chars)
  if not lookup.get("found") or not lookup.get("product"):
    return {"added": False, "reason": "product not found in catalog", "item": None}
  product = lookup["product"]
  return {
    "added": True,
    "item": {
      "name": product.get("name", ""),
      "price": float(product.get("price") or 0),
      "category": product.get("category") or "",
      "brand": product.get("brand") or "",
      "quantity": 1,
    },
  }


def get_user_profile(user_profiles_coll: Collection, user_id: str) -> dict[str, Any]:
  """TODO: find_one on workshop.user_profiles by user_id.

  Solution: scripts/answers/tools.py
  """
  uid = user_id.strip()
  if not uid:
    return {"found": False, "profile": None}
  # TODO: user_profiles_coll.find_one({"user_id": uid}, projection)
  return {"found": False, "profile": None}


def get_purchase_history(
  orders_coll: Collection,
  user_id: str,
  *,
  limit: int = 5,
) -> dict[str, Any]:
  """TODO: find recent orders for this shopper, newest first.

  Solution: scripts/answers/tools.py
  """
  uid = user_id.strip()
  if not uid:
    return {"orders": [], "count": 0}
  # TODO: orders_coll.find({"user_id": uid}).sort("created_at", -1).limit(limit)
  return {"orders": [], "count": 0}


def summarize_purchase_history(orders_coll: Collection, user_id: str) -> dict[str, Any]:
  """TODO (Part 2): $match → $unwind items → $group by items.category.

  Solution: scripts/answers/tools.py
  """
  uid = (user_id or "").strip()
  if not uid:
    return {"categories": [], "count": 0}
  pipeline: list[dict[str, Any]] = [
    {"$match": {"user_id": uid}},
    # TODO: $unwind "items"
    # TODO: $group by items.category — total_spent, item_count
    # TODO: $sort by total_spent desc
    # TODO: $limit 5
  ]
  # TODO: rows = list(orders_coll.aggregate(pipeline))
  # TODO: log_aggregate("orders", pipeline, ...)
  return {"categories": [], "count": 0}


def save_memory(
  memories_coll: Collection,
  *,
  session_id: str,
  user_id: str | None,
  note: str,
  memory_scope: str = MEMORY_SCOPE_LONG_TERM,
) -> dict[str, Any]:
  """TODO: insert_one into workshop.memories (reject SECRET_PATTERNS).

  Solution: scripts/answers/tools.py
  """
  cleaned = note.strip()[:300]
  if not cleaned:
    return {"saved": False, "reason": "empty note"}
  if SECRET_PATTERNS.search(cleaned):
    return {"saved": False, "reason": "note appears to contain sensitive credentials"}
  # TODO: memories_coll.insert_one({session_id, user_id, memory_scope, note, created_at})
  return {"saved": False, "reason": "TODO: insert_one into memories"}


def recall_memory(
  memories_coll: Collection,
  *,
  session_id: str,
  user_id: str | None,
) -> dict[str, Any]:
  """TODO: find session + long-term memories.

  Solution: scripts/answers/tools.py
  """
  # TODO: find memory_scope=session for this session_id
  # TODO: find memory_scope=long_term for this user_id
  return {"session_memories": [], "long_term_memories": [], "count": 0}


def load_conversation_history(
  conversations_coll: Collection,
  *,
  user_id: str,
  session_id: str,
  limit: int = 8,
  max_chars: int = 400,
) -> list[dict[str, str]]:
  """Load recent chat turns for short-term memory (injected into the agent loop)."""
  if not user_id or not session_id:
    return []

  cursor = (
    conversations_coll.find(
      {"user_id": user_id, "session_id": session_id},
      {"_id": 0, "role": 1, "content": 1},
    )
    .sort("created_at", -1)
    .limit(limit)
  )
  turns = list(cursor)
  turns.reverse()

  history: list[dict[str, str]] = []
  for turn in turns:
    role = turn.get("role")
    content = _truncate(str(turn.get("content", "")).strip(), max_chars)
    if role in {"user", "assistant"} and content:
      history.append({"role": role, "content": content})
  return history


def persist_conversation_turn(
  conversations_coll: Collection,
  *,
  user_id: str,
  session_id: str,
  role: str,
  content: str,
  trace: list[dict[str, Any]] | None = None,
) -> None:
  """Append one chat turn to the conversation log."""
  cleaned = str(content or "").strip()
  if not cleaned or role not in {"user", "assistant"}:
    return

  doc: dict[str, Any] = {
    "user_id": user_id,
    "session_id": session_id,
    "role": role,
    "content": cleaned[:2000],
    "created_at": datetime.now(timezone.utc),
  }
  if trace and role == "assistant":
    doc["trace_summary"] = [
      {"step": t.get("step"), "kind": t.get("kind"), "tool": t.get("tool"), "summary": t.get("summary")}
      for t in trace
      if t.get("kind") in {"tool_call", "tool_result", "final"}
    ]
  conversations_coll.insert_one(doc)


def build_tool_registry(
  *,
  knowledge_coll: Collection,
  products_coll: Collection,
  memories_coll: Collection,
  user_profiles_coll: Collection,
  orders_coll: Collection,
  session_id: str,
  user_id: str | None,
  max_result_chars: int,
) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
  """Map allowlisted tool names to callables."""

  def _search(args: dict[str, Any]) -> dict[str, Any]:
    return search_knowledge(knowledge_coll, str(args.get("query", "")), max_chars=max_result_chars)

  def _product(args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("product_name") or args.get("query") or args.get("name") or ""
    return get_product(products_coll, str(query), max_chars=max_result_chars)

  def _compare(args: dict[str, Any]) -> dict[str, Any]:
    names = args.get("products")
    if isinstance(names, list) and len(names) >= 2:
      product_a, product_b = str(names[0]), str(names[1])
    else:
      product_a = str(args.get("product_a") or args.get("product_name_a") or "")
      product_b = str(args.get("product_b") or args.get("product_name_b") or "")
    return compare_products(
      products_coll,
      product_a,
      product_b,
      max_chars=max_result_chars,
    )

  def _cart(args: dict[str, Any]) -> dict[str, Any]:
    return add_to_cart(products_coll, str(args.get("product_name", "")), max_chars=max_result_chars)

  def _profile(_: dict[str, Any]) -> dict[str, Any]:
    if not user_id:
      return {"found": False, "reason": "no user_id in this session"}
    return get_user_profile(user_profiles_coll, user_id)

  def _purchases(args: dict[str, Any]) -> dict[str, Any]:
    if not user_id:
      return {"orders": [], "count": 0, "reason": "no user_id in this session"}
    raw_limit = args.get("limit", 5)
    try:
      limit = max(1, min(10, int(raw_limit)))
    except (TypeError, ValueError):
      limit = 5
    return get_purchase_history(orders_coll, user_id, limit=limit)

  def _summarize(_: dict[str, Any]) -> dict[str, Any]:
    if not user_id:
      return {"categories": [], "count": 0, "reason": "no user_id in this session"}
    return summarize_purchase_history(orders_coll, user_id)

  def _save(args: dict[str, Any]) -> dict[str, Any]:
    scope = str(args.get("memory_scope", MEMORY_SCOPE_LONG_TERM))
    return save_memory(
      memories_coll,
      session_id=session_id,
      user_id=user_id,
      note=str(args.get("note", "")),
      memory_scope=scope,
    )

  def _recall(_: dict[str, Any]) -> dict[str, Any]:
    return recall_memory(memories_coll, session_id=session_id, user_id=user_id)

  return {
    "search_knowledge": _search,
    "get_product": _product,
    "compare_products": _compare,
    "add_to_cart": _cart,
    "get_user_profile": _profile,
    "get_purchase_history": _purchases,
    "summarize_purchase_history": _summarize,
    "save_memory": _save,
    "recall_memory": _recall,
  }
