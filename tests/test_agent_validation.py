"""Agent JSON validation tests."""

import json

import pytest

from agent.agent import should_reject_ungrounded_final
from agent.ollama_client import parse_decision_json


def test_parse_tool_call():
  raw = json.dumps({"type": "tool_call", "tool": "search_knowledge", "arguments": {"query": "returns"}})
  data = parse_decision_json(raw)
  assert data["tool"] == "search_knowledge"


def test_parse_final():
  raw = json.dumps({"type": "final", "answer": "Returns are accepted within 30 days."})
  data = parse_decision_json(raw)
  assert "30 days" in data["answer"]


def test_parse_final_object_answer_coerced_to_string():
  raw = json.dumps({"type": "final", "answer": {"rtx4090": "24GB", "rtx5090": "32GB"}})
  data = parse_decision_json(raw)
  assert isinstance(data["answer"], str)
  assert "5090" in data["answer"]


def test_reject_unknown_type():
  with pytest.raises(ValueError):
    parse_decision_json('{"type": "run_code", "code": "rm -rf /"}')


def test_reject_ungrounded_final_on_policy_question():
  assert should_reject_ungrounded_final(
    "final", tools_used=0, user_message="what is the return policy?"
  )
  assert not should_reject_ungrounded_final(
    "final", tools_used=1, user_message="what is the return policy?"
  )
  assert not should_reject_ungrounded_final(
    "tool_call", tools_used=0, user_message="what is the return policy?"
  )
  assert not should_reject_ungrounded_final("final", tools_used=0, user_message="hi")
