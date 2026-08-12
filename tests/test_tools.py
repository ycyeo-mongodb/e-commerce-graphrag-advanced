"""Tests for LeafyShop support agent tools."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from agent.tools import (
  ALLOWED_TOOLS,
  get_product,
  recall_memory,
  save_memory,
  search_knowledge,
)


def test_allowed_tools_frozen():
  assert "search_knowledge" in ALLOWED_TOOLS
  assert "get_product" in ALLOWED_TOOLS


def test_search_knowledge_returns_shape():
  coll = MagicMock()
  coll.find.return_value.limit.return_value = [
    {"_id": "1", "title": "Returns", "content": "30 day policy", "tags": ["returns"]}
  ]
  result = search_knowledge(coll, "returns", max_chars=500)
  assert result["count"] == 1
  assert result["matches"][0]["title"] == "Returns"


def test_get_product_not_found():
  coll = MagicMock()
  coll.find_one.return_value = None
  result = get_product(coll, "Unknown Widget", max_chars=500)
  assert result["found"] is False


def test_save_memory_rejects_secrets():
  coll = MagicMock()
  result = save_memory(coll, "sess-1", "my password: hunter2")
  assert result["saved"] is False
  coll.insert_one.assert_not_called()


def test_recall_memory_shape():
  coll = MagicMock()
  coll.find.return_value.sort.return_value.limit.return_value = [
    {"note": "concise answers", "created_at": datetime.now(timezone.utc)}
  ]
  result = recall_memory(coll, "sess-1")
  assert result["count"] == 1
  assert result["memories"][0]["note"] == "concise answers"
