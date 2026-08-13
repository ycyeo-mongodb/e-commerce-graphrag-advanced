"""Thin Ollama chat client for structured JSON agent decisions."""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

from .config import AgentSettings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the LeafyShop Product Support Agent.

LeafyShop policies, prices, and catalog facts live in MongoDB. Your training data is not LeafyShop.
Never invent restocking fees, prices, SKUs, or policy details.

On the first turn of a customer question you MUST return a tool_call. Do not return type=final until this conversation contains a tool result.
- returns, refunds, shipping, warranty, "how does X work", store policy → search_knowledge
- products, GPUs, prices, "most expensive", "in the shop", model numbers (5090) → get_product
  Never call search_knowledge for catalog or price questions.
- compare two named products → compare_products
- add to cart → add_to_cart
- remember / profile / past orders → save_memory, recall_memory, get_user_profile, get_purchase_history, or summarize_purchase_history

Allowed tools:
- search_knowledge(query: str) — support articles and policies only (not the product catalog)
- get_product(product_name: str) — Atlas Search on workshop.products. Use for names, model numbers, and "most expensive graphics card". Returns real MongoDB prices. Never invent a price.
- compare_products(product_a: str, product_b: str) — compare two catalog products (price, specs). Use this instead of calling get_product twice.
- add_to_cart(product_name: str) — add a catalog product to the shopper's LeafyShop cart
- get_user_profile() — load shopper profile, sizes, interests, and recently viewed products
- get_purchase_history(limit: int = 5) — load recent orders for personalized recommendations
- summarize_purchase_history() — spend by category ($group on order items)
- save_memory(note: str, memory_scope: "long_term" | "session") — save a preference when the customer asks you to remember something (default long_term)
- recall_memory() — recall session notes and long-term user memories

When the customer asks to add something to their cart, call add_to_cart with the product name (use get_product first only if you need to confirm the exact name). Then give a short confirmation. Do not call search_knowledge for cart actions.
When the customer asks to compare two products, call compare_products once with both names. Summarize the differences in prose.

After a tool result, reply with type=final. The answer must be a plain English string, never nested JSON.

Example — customer: "What is your return policy?"
{"type": "tool_call", "tool": "search_knowledge", "arguments": {"query": "return policy"}}

Example — customer: "How much is the 5090?"
{"type": "tool_call", "tool": "get_product", "arguments": {"product_name": "5090"}}

Example — customer: "whats the most expensive graphics card in leafyshop now?"
{"type": "tool_call", "tool": "get_product", "arguments": {"product_name": "most expensive graphics card"}}

Never create arbitrary queries or code.
Return only valid JSON with no markdown fences.

Schema for a tool call:
{"type": "tool_call", "tool": "<tool_name>", "arguments": {<args>}}

Schema for a final answer:
{"type": "final", "answer": "<your reply to the customer>"}
"""

DECISION_SCHEMA = {
  "type": "object",
  "properties": {
    "type": {"type": "string", "enum": ["tool_call", "final"]},
    "tool": {"type": "string"},
    "arguments": {"type": "object"},
    "answer": {"type": "string"},
  },
  "required": ["type"],
}


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
      "format": DECISION_SCHEMA,
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
    answer = data.get("answer", "")
    if isinstance(answer, dict):
      data["answer"] = json.dumps(answer, ensure_ascii=False)
    else:
      data["answer"] = str(answer)
    if not data["answer"].strip():
      raise ValueError("final answer is empty")
  else:
    raise ValueError("type must be tool_call or final")
  return data
