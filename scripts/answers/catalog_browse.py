"""Answer: GET /api/products — home page find() and category filter.

Attendee lab: backend/catalog_browse.py
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
    filter_expr: dict[str, Any] = {}
    if category:
        filter_expr["category"] = category
    if subcategory:
        filter_expr["subcategory"] = subcategory

    sort_spec = BROWSE_SORTS.get(sort, BROWSE_SORTS["popular"])
    projection = {"description_embedding": 0, "multimodal_embedding": 0}
    cursor = coll.find(filter_expr, projection).sort(sort_spec).limit(limit)
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
