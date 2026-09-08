"""Tests for LeafyShop support agent tools.

Memory / profile / orders bodies stay empty until the Part 2 lab.
get_product is provided (Atlas Search + price sort).
"""

from unittest.mock import MagicMock, patch

from agent.tools import (
  ALLOWED_TOOLS,
  add_to_cart,
  compare_products,
  enrich_product_query,
  get_product,
  get_purchase_history,
  get_user_profile,
  persist_conversation_turn,
  recall_memory,
  save_memory,
  search_knowledge,
  summarize_purchase_history,
)


def test_allowed_tools_frozen():
  assert "search_knowledge" in ALLOWED_TOOLS
  assert "get_product" in ALLOWED_TOOLS
  assert "get_user_profile" in ALLOWED_TOOLS
  assert "get_purchase_history" in ALLOWED_TOOLS
  assert "summarize_purchase_history" in ALLOWED_TOOLS
  assert "add_to_cart" in ALLOWED_TOOLS
  assert "compare_products" in ALLOWED_TOOLS


def test_enrich_product_query_keeps_expensive():
  assert "expensive" in enrich_product_query(
    "graphics card",
    "whats the most expensive graphics card in leafyshop now?",
  ).lower()


@patch("agent.retrieval_starter.vector_search_knowledge")
def test_search_knowledge_returns_shape(mock_vs):
  mock_vs.return_value = [
    {"_id": "1", "title": "Returns", "content": "30 day policy", "tags": ["returns"], "score": 0.8}
  ]
  coll = MagicMock()
  result = search_knowledge(coll, "returns", max_chars=500)
  assert result["count"] == 1
  assert result["mode"] == "vector"
  assert result["matches"][0]["title"] == "Returns"
  mock_vs.assert_called_once_with(coll, "returns", limit=5)
  coll.find.assert_not_called()


@patch("agent.retrieval_starter.vector_search_knowledge")
def test_search_knowledge_natural_language_query(mock_vs):
  mock_vs.return_value = [
    {
      "_id": "2",
      "title": "Returns and refunds policy",
      "content": "LeafyShop accepts returns within 30 days for unused items.",
      "tags": ["returns", "policy", "support"],
      "score": 0.68,
    }
  ]
  coll = MagicMock()
  result = search_knowledge(coll, "what is your returns policy", max_chars=500)
  assert result["count"] == 1
  assert result["mode"] == "vector"
  assert "Returns" in result["matches"][0]["title"]
  mock_vs.assert_called_once()
  coll.find.assert_not_called()


def test_lab_tools_are_empty_until_filled():
  coll = MagicMock()
  assert get_user_profile(coll, "demo_user")["found"] is False
  assert get_purchase_history(coll, "demo_user")["count"] == 0
  assert summarize_purchase_history(coll, "demo_user")["count"] == 0
  assert recall_memory(coll, session_id="s", user_id="demo_user")["count"] == 0
  coll.aggregate.assert_not_called()
  coll.find.assert_not_called()
  coll.find_one.assert_not_called()


def test_get_product_returns_catalog_price():
  coll = MagicMock()
  coll.aggregate.return_value = [
    {
      "name": "NVIDIA GeForce RTX 5090",
      "price": 1999,
      "category": "Components",
      "subcategory": "Graphics Cards",
      "tags": ["gpu", "rtx"],
    }
  ]
  coll.find.return_value.sort.return_value.limit.return_value = []
  coll.find.return_value.limit.return_value = []
  result = get_product(coll, "rtx 5090", max_chars=500)
  assert result["found"] is True
  assert result["product"]["price"] == 1999
  coll.aggregate.assert_called()


def test_get_product_sorts_most_expensive_gpu():
  coll = MagicMock()
  coll.aggregate.return_value = []
  coll.find.return_value.sort.return_value.limit.return_value = [
    {
      "name": "NVIDIA GeForce RTX 5090",
      "price": 2499,
      "category": "Components",
      "subcategory": "Graphics Cards",
      "tags": ["gpu"],
    }
  ]
  result = get_product(coll, "most expensive graphics card", max_chars=500)
  assert result["found"] is True
  assert result["product"]["name"] == "NVIDIA GeForce RTX 5090"
  assert result["mode"] == "atlas_search+price_sort"


def test_add_to_cart_and_compare_use_get_product():
  coll = MagicMock()
  coll.aggregate.side_effect = [
    [{"name": "RTX 5090", "price": 1999, "category": "GPUs", "brand": "NVIDIA", "tags": ["gpu"]}],
    [{"name": "RTX 5080", "price": 999, "category": "GPUs", "brand": "NVIDIA", "tags": ["gpu"]}],
    [{"name": "RTX 5090", "price": 1999, "category": "GPUs", "brand": "NVIDIA", "tags": ["gpu"]}],
  ]
  coll.find.return_value.sort.return_value.limit.return_value = []
  coll.find.return_value.limit.return_value = []
  compared = compare_products(coll, "5090", "5080", max_chars=500)
  assert compared["compared"] is True
  cart = add_to_cart(coll, "5090", max_chars=500)
  assert cart["added"] is True
  assert cart["item"]["name"] == "RTX 5090"


def test_persist_conversation_accepts_non_string():
  coll = MagicMock()
  persist_conversation_turn(
    coll,
    user_id="demo_user",
    session_id="sess-1",
    role="assistant",
    content={"rtx4090": "older", "rtx5090": "newer"},
  )
  coll.insert_one.assert_called_once()
  assert isinstance(coll.insert_one.call_args[0][0]["content"], str)


def test_save_memory_rejects_secrets():
  coll = MagicMock()
  result = save_memory(coll, session_id="sess-1", user_id="demo_user", note="my password: hunter2")
  assert result["saved"] is False
  coll.insert_one.assert_not_called()
