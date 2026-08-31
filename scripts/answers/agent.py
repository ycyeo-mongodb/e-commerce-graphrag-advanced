"""Solution: observe → decide → act agent loop.

Drop-in for backend/agent/agent.py (attendee lab has TODOs for invoking Ollama).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pymongo.collection import Collection

from .config import AgentSettings, load_agent_settings
from .ollama_client import OllamaClient
from .query_log import drain_step_queries, tool_query_scope
from .tools import ALLOWED_TOOLS, build_tool_registry, enrich_product_query, load_conversation_history

logger = logging.getLogger(__name__)

_CHITCHAT = re.compile(
  r"^(hi|hello|hey|yo|thanks|thank you|ok|okay|cool)[\s!.?]*$",
  re.IGNORECASE,
)

UNGROUNDED_RETRY = (
  "You answered without calling a tool. LeafyShop policies and catalog facts are in MongoDB. "
  "Return a tool_call now. For returns, shipping, warranty, or policy questions use "
  'search_knowledge with arguments {"query": "<the customer question>"}. '
  "For products, GPUs, model numbers (5090), prices, or 'most expensive' use "
  'get_product with arguments {"product_name": "<name, model, or category>"}. '
  "Quote the price from the tool result. Do not invent restocking fees or prices."
)

EMPTY_KNOWLEDGE_RETRY = (
  "search_knowledge returned 0 articles. That tool only searches support policies, not the catalog. "
  "If the customer asked about products, GPUs, or prices, call get_product next with "
  'arguments {"product_name": "<copy the customer question, e.g. most expensive graphics card>"}.'
)


def should_reject_ungrounded_final(
  decision_type: str,
  *,
  tools_used: int,
  user_message: str,
) -> bool:
  """llama3.2 often skips tools and answers from memory. Demand a tool_call first."""
  if decision_type != "final":
    return False
  if tools_used > 0:
    return False
  if _CHITCHAT.fullmatch((user_message or "").strip()):
    return False
  return True


class SupportAgent:
  def __init__(
    self,
    *,
    knowledge_coll: Collection,
    products_coll: Collection,
    memories_coll: Collection,
    user_profiles_coll: Collection,
    orders_coll: Collection,
    conversations_coll: Collection,
    session_id: str,
    user_id: str | None = None,
    settings: AgentSettings | None = None,
  ) -> None:
    self.settings = settings or load_agent_settings()
    self.session_id = session_id
    self.user_id = user_id
    self.conversations_coll = conversations_coll
    self.ollama = OllamaClient(self.settings)
    self.tools = build_tool_registry(
      knowledge_coll=knowledge_coll,
      products_coll=products_coll,
      memories_coll=memories_coll,
      user_profiles_coll=user_profiles_coll,
      orders_coll=orders_coll,
      session_id=session_id,
      user_id=user_id,
      max_result_chars=self.settings.max_tool_result_chars,
    )
    self.trace: list[dict[str, Any]] = []
    self.cart_items: list[dict[str, Any]] = []

  def run(self, user_message: str) -> dict[str, Any]:
    """Run the agent loop for one customer message."""
    message = user_message.strip()
    if not message:
      return self._reply("Please enter a question.")
    if len(message) > self.settings.max_query_length:
      return self._reply(f"Message too long (max {self.settings.max_query_length} characters).")

    messages: list[dict[str, str]] = []
    if self.user_id and self.conversations_coll is not None:
      prior = load_conversation_history(
        self.conversations_coll,
        user_id=self.user_id,
        session_id=self.session_id,
        limit=8,
        max_chars=400,
      )
      messages.extend(prior)
    messages.append({"role": "user", "content": message})
    tools_used = 0

    for step in range(1, self.settings.max_iterations + 1):
      try:
        decision = self.ollama.decide(messages)
      except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Invalid JSON from model (attempt 1): %s", exc)
        messages.append(
          {
            "role": "user",
            "content": (
              "Your previous response was invalid JSON. "
              'Return only {"type":"tool_call",...} or {"type":"final",...}.'
            ),
          }
        )
        try:
          decision = self.ollama.decide(messages)
        except (json.JSONDecodeError, ValueError) as retry_exc:
          self._trace(step, "error", summary=str(retry_exc))
          return self._reply("Sorry, I could not process that request. Please try rephrasing.")

      if decision["type"] == "final":
        if should_reject_ungrounded_final(
          decision["type"],
          tools_used=tools_used,
          user_message=message,
        ):
          logger.info("Rejecting ungrounded final; demanding a tool_call")
          messages.append({"role": "user", "content": UNGROUNDED_RETRY})
          continue
        self._trace(step, "final", summary="answer ready")
        return self._reply(decision["answer"])

      tool_name = decision["tool"]
      if tool_name not in ALLOWED_TOOLS:
        self._trace(step, "error", tool=tool_name, summary="unknown tool rejected")
        return self._reply("I tried to use a tool that is not allowed. Please try again.")

      arguments = decision.get("arguments", {})
      if tool_name == "get_product":
        arguments = dict(arguments or {})
        arguments["product_name"] = enrich_product_query(
          str(arguments.get("product_name") or arguments.get("query") or arguments.get("name") or ""),
          message,
        )
      self._trace(step, "tool_call", tool=tool_name, arguments=arguments)

      try:
        with tool_query_scope():
          result = self.tools[tool_name](arguments)
          mongodb_queries = drain_step_queries()
      except Exception as exc:  # noqa: BLE001 — surface safe tool errors to the model
        logger.exception("Tool %s failed", tool_name)
        result = {"error": "tool execution failed", "detail": str(exc)[:200]}
        mongodb_queries = []
      tools_used += 1
      if tool_name == "add_to_cart" and result.get("added") and result.get("item"):
        self.cart_items.append(result["item"])
      summary = _summarize_tool_result(tool_name, result)
      self._trace(
        step,
        "tool_result",
        tool=tool_name,
        summary=summary,
        mongodb_queries=mongodb_queries,
      )

      messages.append(
        {
          "role": "assistant",
          "content": json.dumps({"type": "tool_call", "tool": tool_name, "arguments": arguments}),
        }
      )
      messages.append(
        {
          "role": "user",
          "content": f"Tool result for {tool_name}: {json.dumps(result)[: self.settings.max_tool_result_chars]}",
        }
      )
      if tool_name == "search_knowledge" and not result.get("count"):
        messages.append({"role": "user", "content": EMPTY_KNOWLEDGE_RETRY})

    self._trace(self.settings.max_iterations + 1, "error", summary="iteration limit reached")
    return self._reply(
      "I need more steps than allowed to finish this request. Please ask a simpler question."
    )

  def _reply(self, answer: Any) -> dict[str, Any]:
    if isinstance(answer, dict):
      text = json.dumps(answer, ensure_ascii=False)
    else:
      text = str(answer or "")
    return {"answer": text, "trace": self.trace, "cart_items": list(self.cart_items)}

  def _trace(
    self,
    step: int,
    kind: str,
    *,
    tool: str | None = None,
    arguments: dict[str, Any] | None = None,
    summary: str | None = None,
    mongodb_queries: list[dict[str, Any]] | None = None,
  ) -> None:
    entry: dict[str, Any] = {"step": step, "kind": kind}
    if tool:
      entry["tool"] = tool
    if arguments is not None:
      entry["arguments"] = arguments
    if summary:
      entry["summary"] = summary
    if mongodb_queries:
      entry["mongodb_queries"] = mongodb_queries
    self.trace.append(entry)
    logger.info("[step %s] %s", step, entry)


def build_agent_trace(trace: list[dict[str, Any]], *, latency_ms: float | None = None) -> dict[str, Any]:
  """Shape trace events for the chat UI (grouped tool steps + MongoDB ops)."""
  tool_calls = 0
  steps: list[dict[str, Any]] = []
  pending: dict[int, dict[str, Any]] = {}

  for entry in trace:
    step = entry.get("step", 0)
    kind = entry.get("kind")

    if kind == "tool_call":
      tool_calls += 1
      pending[step] = {
        "step": step,
        "tool": entry.get("tool"),
        "arguments": entry.get("arguments", {}),
        "mongodb_queries": [],
        "result_summary": None,
      }
      continue

    if kind == "tool_result" and step in pending:
      pending[step]["result_summary"] = entry.get("summary")
      pending[step]["mongodb_queries"] = entry.get("mongodb_queries") or []
      steps.append(pending.pop(step))
      continue

    if kind == "final":
      steps.append({"step": step, "kind": "final", "summary": entry.get("summary", "answer ready")})
    elif kind == "error":
      steps.append({"step": step, "kind": "error", "summary": entry.get("summary", "error")})

  for leftover in pending.values():
    steps.append(leftover)

  steps.sort(key=lambda s: s.get("step", 0))
  payload: dict[str, Any] = {"tool_calls": tool_calls, "steps": steps}
  if latency_ms is not None:
    payload["latency_ms"] = round(latency_ms, 1)
  return payload


def _summarize_tool_result(tool_name: str, result: dict[str, Any]) -> str:
  if tool_name == "search_knowledge":
    return f"{result.get('count', 0)} matching documents"
  if tool_name == "get_product":
    product = result.get("product") or {}
    if result.get("found"):
      name = product.get("name") or "product"
      price = product.get("price")
      extra = f" (+{result['count'] - 1} more)" if result.get("count", 1) > 1 else ""
      if price is not None:
        return f"{name} ${price}{extra}"
      return f"{name}{extra}"
    return "product not found"
  if tool_name == "compare_products":
    if result.get("compared"):
      left = (result.get("product_a") or {}).get("name") or "A"
      right = (result.get("product_b") or {}).get("name") or "B"
      return f"compared {left} vs {right}"
    missing = result.get("missing") or []
    return "missing: " + ", ".join(str(m) for m in missing) if missing else "not compared"
  if tool_name == "add_to_cart":
    if result.get("added"):
      name = (result.get("item") or {}).get("name") or "item"
      return f"added {name}"
    return result.get("reason", "not added")
  if tool_name == "get_user_profile":
    return "profile loaded" if result.get("found") else "profile not found"
  if tool_name == "get_purchase_history":
    return f"{result.get('count', 0)} orders"
  if tool_name == "summarize_purchase_history":
    return f"{result.get('count', 0)} categories"
  if tool_name == "save_memory":
    return "saved" if result.get("saved") else result.get("reason", "not saved")
  if tool_name == "recall_memory":
    return f"{result.get('count', 0)} memories"
  return "completed"
