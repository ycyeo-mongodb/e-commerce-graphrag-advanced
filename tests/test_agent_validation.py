"""Agent JSON validation tests."""

import json

import pytest

from agent.ollama_client import parse_decision_json


def test_parse_tool_call():
  raw = json.dumps({"type": "tool_call", "tool": "search_knowledge", "arguments": {"query": "returns"}})
  data = parse_decision_json(raw)
  assert data["tool"] == "search_knowledge"


def test_parse_final():
  raw = json.dumps({"type": "final", "answer": "Returns are accepted within 30 days."})
  data = parse_decision_json(raw)
  assert "30 days" in data["answer"]


def test_reject_unknown_type():
  with pytest.raises(ValueError):
    parse_decision_json('{"type": "run_code", "code": "rm -rf /"}')
