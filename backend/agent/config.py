"""Agent configuration from environment variables."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSettings:
    ollama_host: str
    ollama_model: str
    max_iterations: int
    max_query_length: int
    max_tool_result_chars: int


def load_agent_settings() -> AgentSettings:
    return AgentSettings(
        ollama_host=os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "llama3.2"),
        max_iterations=int(os.environ.get("AGENT_MAX_ITERATIONS", "6")),
        max_query_length=int(os.environ.get("AGENT_MAX_QUERY_LENGTH", "500")),
        max_tool_result_chars=int(os.environ.get("AGENT_MAX_TOOL_RESULT_CHARS", "4000")),
    )
