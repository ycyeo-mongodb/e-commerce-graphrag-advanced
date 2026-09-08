"""Allowlisted tools for the LeafyShop support agent.

Part 2 lab: fill the MongoDB bodies (save_memory, recall_memory,
summarize_purchase_history, plus profile / orders). Solution: scripts/answers/tools.py

get_product is provided (Atlas Search + price sort). search_knowledge is already wired
to retrieval_starter.py — fill that file in the RAG lab.
"""

from __future__ import annotations

import re
import time
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

_STOP_WORDS = frozenset({
  "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
  "what", "how", "do", "does", "did", "can", "could", "would", "should",
  "your", "my", "i", "me", "we", "our", "you", "they", "their", "it", "its",
  "about", "for", "on", "in", "to", "of", "and", "or", "tell", "please",
  "have", "has", "had", "get", "give", "know", "like", "want", "need",
})

_CATALOG_NOISE = _STOP_WORDS | frozenset({
  "most", "least", "expensive", "cheapest", "cheap", "highest", "lowest",
  "price", "priced", "cost", "available", "leafyshop", "shop", "now",
  "current", "currently", "best", "top", "whats", "what's",
})

_PRICE_DESC = re.compile(
  r"\b(most expensive|expensive|highest|priciest|premium|flagship)\b",
  re.IGNORECASE,
)
_PRICE_ASC = re.compile(
  r"\b(cheapest|least expensive|lowest|affordable|budget|inexpensive)\b",
  re.IGNORECASE,
)


def _catalog_search_query(raw: str) -> str:
  """Drop ranking chatter so Atlas Search matches 'graphics card', not 'most expensive'."""
  words = re.findall(r"[a-z0-9]+", raw.lower())
  keep = [w for w in words if w not in _CATALOG_NOISE and len(w) >= 2]
  return " ".join(keep) or raw.strip()


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


def _product_card(doc: dict[str, Any], *, max_chars: int) -> dict[str, Any]:
  """Catalog fields the agent is allowed to quote — always includes price."""
  card: dict[str, Any] = {
    "name": doc.get("name"),
    "price": doc.get("price"),
    "category": doc.get("category"),
    "subcategory": doc.get("subcategory"),
    "brand": doc.get("brand"),
    "in_stock": doc.get("in_stock"),
    "tags": doc.get("tags") or [],
    "spec_highlights": doc.get("spec_highlights") or [],
    "specs": doc.get("specs") or {},
  }
  if doc.get("description"):
    card["description"] = _truncate(str(doc["description"]), max_chars)
  return card


def _catalog_find_fallback(
  products_coll: Collection,
  query: str,
  *,
  projection: dict[str, Any],
  limit: int,
) -> list[dict[str, Any]]:
  """Substring match on name / tags / description when $search misses (e.g. '5090')."""
  rx = re.compile(re.escape(query), re.IGNORECASE)
  filter_doc = {"$or": [{"name": rx}, {"tags": rx}, {"description": rx}]}
  log_filter = {
    "$or": [
      {"name": {"$regex": query, "$options": "i"}},
      {"tags": {"$regex": query, "$options": "i"}},
      {"description": {"$regex": query, "$options": "i"}},
    ]
  }
  t0 = time.perf_counter()
  docs = list(products_coll.find(filter_doc, projection).limit(limit))
  log_find(
    "products",
    log_filter,
    label=f"Catalog find — {query}",
    projection=projection,
    limit=limit,
    latency_ms=(time.perf_counter() - t0) * 1000,
    result_count=len(docs),
  )
  return docs


def _catalog_by_price(
  products_coll: Collection,
  query: str,
  *,
  projection: dict[str, Any],
  limit: int,
  direction: int,
) -> list[dict[str, Any]]:
  """Find catalog matches and sort by price. Atlas Search cannot sort on price
  until `price` is a number field on text_search_index."""
  terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) >= 3]
  if any(t in {"graphics", "gpu", "gpus"} for t in terms):
    terms = [t for t in terms if t not in {"card", "cards"}]
  if not terms:
    return []
  or_clauses: list[dict[str, Any]] = []
  log_clauses: list[dict[str, Any]] = []
  for term in terms:
    rx = re.compile(re.escape(term), re.IGNORECASE)
    or_clauses.extend([
      {"name": rx},
      {"subcategory": rx},
      {"tags": rx},
      {"category": rx},
    ])
    log_clauses.extend([
      {"name": {"$regex": term, "$options": "i"}},
      {"subcategory": {"$regex": term, "$options": "i"}},
      {"tags": {"$regex": term, "$options": "i"}},
      {"category": {"$regex": term, "$options": "i"}},
    ])
  filter_doc = {"$or": or_clauses}
  sort_spec = [("price", direction)]
  t0 = time.perf_counter()
  docs = list(products_coll.find(filter_doc, projection).sort(sort_spec).limit(limit))
  log_find(
    "products",
    {"$or": log_clauses},
    label=f"Catalog by price — {query}",
    projection=projection,
    sort=sort_spec,
    limit=limit,
    latency_ms=(time.perf_counter() - t0) * 1000,
    result_count=len(docs),
  )
  return docs


def _dedupe_products(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
  seen: set[str] = set()
  out: list[dict[str, Any]] = []
  for doc in docs:
    key = str(doc.get("name") or "")
    if not key or key in seen:
      continue
    seen.add(key)
    out.append(doc)
  return out


def get_product(products_coll: Collection, product_name: str, *, max_chars: int) -> dict[str, Any]:
  """Search workshop.products with Atlas Search ($search on text_search_index).

  Price questions (most expensive / cheapest) also sort MongoDB `price`.
  """
  raw = product_name.strip()[:200]
  if not raw:
    return {"found": False, "product": None, "matches": [], "count": 0, "mode": "atlas_search"}

  search_query = _catalog_search_query(raw)
  price_dir = _price_sort_direction(raw)
  find_projection = {
    "_id": 0,
    "name": 1,
    "category": 1,
    "subcategory": 1,
    "description": 1,
    "price": 1,
    "brand": 1,
    "in_stock": 1,
    "tags": 1,
    "spec_highlights": 1,
    "specs": 1,
  }
  search_projection = {**find_projection, "score": {"$meta": "searchScore"}}
  atlas_limit = 25 if price_dir is not None else CATALOG_SEARCH_LIMIT
  pipeline = [
    {
      "$search": {
        "index": PRODUCT_TEXT_INDEX,
        "compound": {
          "should": [
            {
              "text": {
                "query": search_query,
                "path": "name",
                "score": {"boost": {"value": 5}},
              }
            },
            {
              "text": {
                "query": search_query,
                "path": "name",
                "fuzzy": {"maxEdits": 1, "prefixLength": 2},
              }
            },
            {
              "text": {
                "query": search_query,
                "path": "description",
                "score": {"boost": {"value": 1}},
              }
            },
          ],
          "minimumShouldMatch": 1,
        },
      }
    },
    {"$limit": atlas_limit},
    {"$project": search_projection},
  ]

  t0 = time.perf_counter()
  try:
    atlas_docs = list(products_coll.aggregate(pipeline))
  except Exception:  # noqa: BLE001 — fall back to find() if the search index is missing
    atlas_docs = []
  log_aggregate(
    "products",
    pipeline,
    label=f"Atlas Search — {search_query}",
    latency_ms=(time.perf_counter() - t0) * 1000,
    result_count=len(atlas_docs),
  )

  gpu_query = bool(re.search(r"\b(graphics|gpu|gpus|rtx|radeon|geforce)\b", f"{raw} {search_query}", re.I))
  if gpu_query and atlas_docs:
    gpu_hits = []
    for doc in atlas_docs:
      blob = " ".join([
        str(doc.get("subcategory") or ""),
        str(doc.get("category") or ""),
        str(doc.get("name") or ""),
        " ".join(str(t) for t in (doc.get("tags") or [])),
      ]).lower()
      if any(tok in blob for tok in ("graphics", "gpu", "rtx", "geforce", "radeon")):
        gpu_hits.append(doc)
    if gpu_hits:
      atlas_docs = gpu_hits

  docs = list(atlas_docs)
  mode = "atlas_search"
  if price_dir is not None:
    priced = _catalog_by_price(
      products_coll,
      search_query,
      projection=find_projection,
      limit=CATALOG_SEARCH_LIMIT,
      direction=price_dir,
    )
    if priced:
      docs = priced
      mode = "atlas_search+price_sort"
    elif atlas_docs:
      docs = sorted(
        atlas_docs,
        key=lambda d: float(d.get("price") or 0),
        reverse=(price_dir < 0),
      )
      mode = "atlas_search+price_sort"
  if not docs:
    docs = _catalog_find_fallback(
      products_coll,
      search_query,
      projection=find_projection,
      limit=CATALOG_SEARCH_LIMIT,
    )
    if docs:
      mode = "find"

  docs = _dedupe_products(docs)[:CATALOG_SEARCH_LIMIT]
  if not docs:
    return {"found": False, "product": None, "matches": [], "count": 0, "mode": mode}

  matches = [_product_card(doc, max_chars=max_chars) for doc in docs]
  return {
    "found": True,
    "product": matches[0],
    "matches": matches,
    "count": len(matches),
    "mode": mode,
  }


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
  field = "???"  # TODO — the profile key that matches demo_user (user_id)
  if field == "???":
    return {"found": False, "profile": None}
  t0 = time.perf_counter()
  doc = user_profiles_coll.find_one({field: uid}, {"_id": 0})
  log_find(
    "user_profiles",
    {field: uid},
    label=f"Load shopper profile — {uid}",
    projection={"_id": 0},
    latency_ms=(time.perf_counter() - t0) * 1000,
    result_count=1 if doc else 0,
    operation="findOne",
  )
  if not doc:
    return {"found": False, "profile": None}
  return {"found": True, "profile": doc}


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
  field = "???"       # TODO — user_id
  sort_field = "???"  # TODO — created_at
  if "???" in (field, sort_field):
    return {"orders": [], "count": 0}
  t0 = time.perf_counter()
  docs = list(orders_coll.find({field: uid}, {"_id": 1, "items": 1, "total": 1, "created_at": 1, "item_count": 1}).sort(sort_field, -1).limit(limit))
  log_find(
    "orders",
    {field: uid},
    label=f"Purchase history — {uid}",
    sort=[(sort_field, -1)],
    limit=limit,
    latency_ms=(time.perf_counter() - t0) * 1000,
    result_count=len(docs),
  )
  orders = []
  for doc in docs:
    created = doc.get("created_at")
    items = [
      {"name": item.get("name", ""), "quantity": item.get("quantity", 1), "price": item.get("price", 0)}
      for item in (doc.get("items") or [])
    ]
    orders.append(
      {
        "order_id": str(doc.get("_id", "")),
        "total": doc.get("total", 0),
        "item_count": doc.get("item_count", len(items)),
        "items": items,
        "created_at": created.isoformat() if created and hasattr(created, "isoformat") else created,
      }
    )
  return {"orders": orders, "count": len(orders)}


def summarize_purchase_history(orders_coll: Collection, user_id: str) -> dict[str, Any]:
  """TODO (Part 2): $match → $unwind items → $group by items.category.

  Solution: scripts/answers/tools.py
  """
  uid = (user_id or "").strip()
  if not uid:
    return {"categories": [], "count": 0}
  pipeline: list[dict[str, Any]] = [
    {"$match": {"user_id": uid}},
    {"$unwind": "???"},  # TODO — "$items"
    {
      "$group": {
        "_id": "???",  # TODO — "$items.category"
        "total_spent": {"$sum": {"$multiply": ["$items.price", "$items.quantity"]}},
        "item_count": {"$sum": "$items.quantity"},
      }
    },
    {"$sort": {"total_spent": -1}},
    {"$limit": 5},
  ]
  if pipeline[1].get("$unwind") == "???" or pipeline[2]["$group"]["_id"] == "???":
    return {"categories": [], "count": 0}
  t0 = time.perf_counter()
  rows = list(orders_coll.aggregate(pipeline))
  log_aggregate(
    "orders",
    pipeline,
    label=f"Purchase summary by category — {uid}",
    latency_ms=(time.perf_counter() - t0) * 1000,
    result_count=len(rows),
  )
  categories = [
    {
      "category": row.get("_id") or "Unknown",
      "total_spent": row.get("total_spent") or 0,
      "item_count": row.get("item_count") or 0,
    }
    for row in rows
  ]
  return {"categories": categories, "count": len(categories)}


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
  scope = memory_scope if memory_scope in {MEMORY_SCOPE_SESSION, MEMORY_SCOPE_LONG_TERM} else MEMORY_SCOPE_LONG_TERM
  if scope == MEMORY_SCOPE_LONG_TERM and not user_id:
    scope = MEMORY_SCOPE_SESSION
  doc: dict[str, Any] = {
    "session_id": session_id,
    "memory_scope": scope,
    "note": cleaned,
    "created_at": datetime.now(timezone.utc),
  }
  if user_id:
    doc["user_id"] = user_id
  mongo_op = "???"  # TODO — insert_one
  if mongo_op != "insert_one":
    return {"saved": False, "reason": "TODO: insert_one into memories"}
  t0 = time.perf_counter()
  result = memories_coll.insert_one(doc)
  log_doc = {k: v for k, v in doc.items()}
  if isinstance(log_doc.get("created_at"), datetime):
    log_doc["created_at"] = log_doc["created_at"].isoformat()
  log_insert_one("memories", log_doc, label=f"Save {scope} memory", latency_ms=(time.perf_counter() - t0) * 1000)
  return {"saved": True, "id": str(result.inserted_id), "memory_scope": scope}


def recall_memory(
  memories_coll: Collection,
  *,
  session_id: str,
  user_id: str | None,
) -> dict[str, Any]:
  """TODO: find session + long-term memories.

  Solution: scripts/answers/tools.py
  """
  session_scope = "???"     # TODO — session
  long_term_scope = "???"  # TODO — long_term
  if "???" in (session_scope, long_term_scope):
    return {"session_memories": [], "long_term_memories": [], "count": 0}

  def _notes(query: dict[str, Any], *, limit: int, label: str) -> list[dict[str, Any]]:
    t0 = time.perf_counter()
    raw = list(
      memories_coll.find(query, {"_id": 0, "note": 1, "created_at": 1, "memory_scope": 1})
      .sort("created_at", -1)
      .limit(limit)
    )
    log_find(
      "memories",
      query,
      label=label,
      projection={"_id": 0, "note": 1, "created_at": 1, "memory_scope": 1},
      sort=[("created_at", -1)],
      limit=limit,
      latency_ms=(time.perf_counter() - t0) * 1000,
      result_count=len(raw),
    )
    notes = []
    for row in raw:
      created = row.get("created_at")
      notes.append(
        {
          "note": row.get("note", ""),
          "memory_scope": row.get("memory_scope"),
          "created_at": created.isoformat() if created and hasattr(created, "isoformat") else created,
        }
      )
    return notes

  session_notes = _notes(
    {"session_id": session_id, "memory_scope": session_scope},
    limit=5,
    label="Recall session memories",
  )
  long_term_notes: list[dict[str, Any]] = []
  if user_id:
    long_term_notes = _notes(
      {"user_id": user_id, "memory_scope": long_term_scope},
      limit=10,
      label=f"Recall long-term memories — {user_id}",
    )
  return {
    "session_memories": session_notes,
    "long_term_memories": long_term_notes,
    "count": len(session_notes) + len(long_term_notes),
  }


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
