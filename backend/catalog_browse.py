"""GET /api/products — the LeafyShop home page and category sidebar.

These are ordinary MongoDB find() queries, not $vectorSearch.

    GET /api/products                      → 1a empty filter (home page)
    GET /api/products?category=Electronics → 1b filter on category (sidebar)

app.py already calls browse_products on page load. Fill the TODOs, restart uvicorn,
reload the shop. Until then the grid is empty (search bar is a different endpoint).

Solution: scripts/answers/catalog_browse.py
"""

from __future__ import annotations

from typing import Any, Optional

from pymongo.collection import Collection

BROWSE_SORTS = {
  "popular": [("reviews_count", -1), ("rating", -1)],
  "rating": [("rating", -1), ("reviews_count", -1)],
  "newest": [("id", -1)],
  "price_asc": [("price", 1)],
  "price_desc": [("price", -1)],
}


def browse_products(
  coll: Collection,
  *,
  category: Optional[str] = None,
  subcategory: Optional[str] = None,
  sort: str = "popular",
  limit: int = 12,
) -> list[dict[str, Any]]:
  """Called by GET /api/products on page load and sidebar clicks."""
  filter_expr: dict[str, Any] = {}

  # TODO 1b — sidebar: GET /api/products?category=Electronics
  # If category (or subcategory) is set, add it to the filter document.
  #     if category:
  #         filter_expr["???"] = category

  sort_spec = BROWSE_SORTS.get(sort, BROWSE_SORTS["popular"])
  projection = {"description_embedding": 0, "multimodal_embedding": 0}

  # TODO 1a — home page: GET /api/products
  # Empty filter_expr + find().sort().limit() loads the featured grid.
  cursor = None  # TODO: coll.find(filter_expr, projection).sort(sort_spec).limit(limit)
  if cursor is None:
    return []

  return _serialize(cursor)


def _serialize(cursor) -> list[dict[str, Any]]:
  results = []
  for doc in cursor:
    doc.pop("_id", None)
    for k, v in list(doc.items()):
      if isinstance(v, float):
        doc[k] = round(v, 4)
    results.append(doc)
  return results


if __name__ == "__main__":
  import os

  from dotenv import load_dotenv
  from pymongo import MongoClient

  load_dotenv()
  client = MongoClient(os.environ["MONGODB_URI"])
  coll = client["workshop"]["products"]

  print("browse_products (your TODOs)")

  print("\n1a  Home page  GET /api/products")
  home = browse_products(coll, limit=12)
  print(f"  {len(home)} products")
  for p in home[:5]:
    print(f"    {p.get('name')}  [{p.get('category')}]")

  print("\n1b  Sidebar   GET /api/products?category=Electronics")
  electronics = browse_products(coll, category="Electronics", limit=12)
  print(f"  {len(electronics)} products")
  for p in electronics[:5]:
    print(f"    {p.get('name')}  [{p.get('category')}]")
  if electronics and any(p.get("category") != "Electronics" for p in electronics):
    print("  Warning: 1b should only return Electronics — check the filter field.")

  client.close()
