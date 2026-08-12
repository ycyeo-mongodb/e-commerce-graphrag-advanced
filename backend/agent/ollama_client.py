"""Thin Ollama chat client for structured JSON agent decisions."""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

from .config import AgentSettings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the LeafyShop Product Support Agent.

You help customers with product compatibility, support policies, shipping, and returns.
You may answer directly only when you already have enough information in the conversation.
When information is missing, select exactly one tool from the allowed tool list.

Allowed tools:
- search_knowledge(query: str) — search support articles and policies
- get_product(product_name: str) — look up a catalog product by name
- save_memory(note: str) — save a user preference when they explicitly ask you to remember something
- recall_memory() — recall saved preferences for this session

Never invent database results.
Never create arbitrary queries or code.
Return only valid JSON with no markdown fences.

Schema for a tool call:
{"type": "tool_call", "tool": "<tool_name>", "arguments": {<args>}}

Schema for a final answer:
{"type": "final", "answer": "<your reply to the customer>"}
"""


class OllamaClient:
  def __init__(self, settings: AgentSettings) -> None:
    self.settings = settings

  def decide(self, messages: list[dict[str, str]]) -> dict[str, Any]:
    """Ask Ollama for the next agent decision as JSON."""
    url = f"{self.settings.ollama_host}/api/chat"
    payload = {
      "model": self.settings.ollama_model,
      "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
      "stream": False,
      "format": "json",
    }
    try:
      response = requests.post(url, json=payload, timeout=120)
      response.raise_for_status()
    except requests.RequestException as exc:
      raise ConnectionError(
        "Could not reach Ollama. Install from https://ollama.com and run: ollama pull llama3.2"
      ) from exc

    content = (response.json().get("message") or {}).get("content", "")
    return parse_decision_json(content)


def parse_decision_json(raw: str) -> dict[str, Any]:
  """Parse and validate the model's JSON decision."""
  text = raw.strip()
  if text.startswith("```"):
    text = text.strip("`")
    if text.lower().startswith("json"):
      text = text[4:].strip()
  data = json.loads(text)
  if not isinstance(data, dict):
    raise ValueError("Decision must be a JSON object")
  decision_type = data.get("type")
  if decision_type == "tool_call":
    if not data.get("tool"):
      raise ValueError("tool_call missing tool name")
    if not isinstance(data.get("arguments", {}), dict):
      raise ValueError("tool_call arguments must be an object")
  elif decision_type == "final":
    if not str(data.get("answer", "")).strip():
      raise ValueError("final answer is empty")
  else:
    raise ValueError("type must be tool_call or final")
  return data
