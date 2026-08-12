"""Explicit observe → decide → act agent loop for LeafyShop support."""

from __future__ import annotations

import json
import logging
from typing import Any

from pymongo.collection import Collection

from .config import AgentSettings, load_agent_settings
from .ollama_client import OllamaClient
from .tools import ALLOWED_TOOLS, build_tool_registry

logger = logging.getLogger(__name__)


class SupportAgent:
  def __init__(
    self,
    *,
    knowledge_coll: Collection,
    products_coll: Collection,
    memories_coll: Collection,
    session_id: str,
    settings: AgentSettings | None = None,
  ) -> None:
    self.settings = settings or load_agent_settings()
    self.session_id = session_id
    self.ollama = OllamaClient(self.settings)
    self.tools = build_tool_registry(
      knowledge_coll=knowledge_coll,
      products_coll=products_coll,
      memories_coll=memories_coll,
      session_id=session_id,
      max_result_chars=self.settings.max_tool_result_chars,
    )
    self.trace: list[dict[str, Any]] = []

  def run(self, user_message: str) -> dict[str, Any]:
    """Run the agent loop for one customer message."""
    message = user_message.strip()
    if not message:
      return {"answer": "Please enter a question.", "trace": []}
    if len(message) > self.settings.max_query_length:
      return {
        "answer": f"Message too long (max {self.settings.max_query_length} characters).",
        "trace": [],
      }

    messages: list[dict[str, str]] = [{"role": "user", "content": message}]

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
          return {
            "answer": "Sorry, I could not process that request. Please try rephrasing.",
            "trace": self.trace,
          }

      if decision["type"] == "final":
        self._trace(step, "final", summary="answer ready")
        return {"answer": decision["answer"], "trace": self.trace}

      tool_name = decision["tool"]
      if tool_name not in ALLOWED_TOOLS:
        self._trace(step, "error", tool=tool_name, summary="unknown tool rejected")
        return {
          "answer": "I tried to use a tool that is not allowed. Please try again.",
          "trace": self.trace,
        }

      arguments = decision.get("arguments", {})
      self._trace(step, "tool_call", tool=tool_name, arguments=arguments)

      try:
        result = self.tools[tool_name](arguments)
      except Exception as exc:  # noqa: BLE001 — surface safe tool errors to the model
        logger.exception("Tool %s failed", tool_name)
        result = {"error": "tool execution failed", "detail": str(exc)[:200]}

      summary = _summarize_tool_result(tool_name, result)
      self._trace(step, "tool_result", tool=tool_name, summary=summary)

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

    self._trace(self.settings.max_iterations + 1, "error", summary="iteration limit reached")
    return {
      "answer": "I need more steps than allowed to finish this request. Please ask a simpler question.",
      "trace": self.trace,
    }

  def _trace(
    self,
    step: int,
    kind: str,
    *,
    tool: str | None = None,
    arguments: dict[str, Any] | None = None,
    summary: str | None = None,
  ) -> None:
    entry: dict[str, Any] = {"step": step, "kind": kind}
    if tool:
      entry["tool"] = tool
    if arguments is not None:
      entry["arguments"] = arguments
    if summary:
      entry["summary"] = summary
    self.trace.append(entry)
    logger.info("[step %s] %s", step, entry)


def _summarize_tool_result(tool_name: str, result: dict[str, Any]) -> str:
  if tool_name == "search_knowledge":
    return f"{result.get('count', 0)} matching documents"
  if tool_name == "get_product":
    return "product found" if result.get("found") else "product not found"
  if tool_name == "save_memory":
    return "saved" if result.get("saved") else result.get("reason", "not saved")
  if tool_name == "recall_memory":
    return f"{result.get('count', 0)} memories"
  return "completed"
