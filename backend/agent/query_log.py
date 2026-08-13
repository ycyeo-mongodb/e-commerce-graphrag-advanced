"""In-memory MongoDB query log for the Live Inspector and agent trace."""

from __future__ import annotations

import json
import os
import time
import uuid
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from threading import Lock
from typing import Any, Iterator
from urllib.parse import urlparse

_DB_NAME = "workshop"
_MAX_ENTRIES = 200
_LOG_FILE = Path(__file__).resolve().parent.parent / ".query_log.json"

_lock = Lock()
_active_session: str | None = None
_step_queries: ContextVar[list[dict[str, Any]] | None] = ContextVar("step_queries", default=None)


def _hydrate() -> deque[dict[str, Any]]:
  """Reload the inspector log after uvicorn --reload wipes the process."""
  if not _LOG_FILE.exists():
    return deque(maxlen=_MAX_ENTRIES)
  try:
    raw = json.loads(_LOG_FILE.read_text())
    if not isinstance(raw, list):
      return deque(maxlen=_MAX_ENTRIES)
    items = [row for row in raw if isinstance(row, dict)]
    return deque(items[:_MAX_ENTRIES], maxlen=_MAX_ENTRIES)
  except (OSError, json.JSONDecodeError, TypeError):
    return deque(maxlen=_MAX_ENTRIES)


_log: deque[dict[str, Any]] = _hydrate()


def _flush() -> None:
  try:
    with _lock:
      payload = list(_log)
    _LOG_FILE.write_text(json.dumps(payload, default=str))
  except OSError:
    pass


def set_active_session(session_id: str | None) -> None:
  global _active_session
  _active_session = session_id


def get_cluster_label() -> str:
  uri = os.environ.get("MONGODB_URI", "")
  try:
    host = urlparse(uri).hostname or "Atlas"
    return host.split(".")[0] if host else "Atlas"
  except Exception:
    return "Atlas"


def _pretty(value: Any) -> str:
  return json.dumps(value, indent=2, default=str)


def _json_safe(value: Any) -> Any:
  if isinstance(value, dict):
    return {str(k): _json_safe(v) for k, v in value.items()}
  if isinstance(value, (list, tuple)):
    return [_json_safe(v) for v in value]
  if isinstance(value, (str, int, float, bool)) or value is None:
    return value
  return str(value)


def _push(entry: dict[str, Any]) -> dict[str, Any]:
  entry = _json_safe(entry)
  with _lock:
    _log.appendleft(entry)
  bucket = _step_queries.get()
  if bucket is not None:
    bucket.append(entry)
  _flush()
  return entry


@contextmanager
def tool_query_scope() -> Iterator[None]:
  token = _step_queries.set([])
  try:
    yield
  finally:
    _step_queries.reset(token)


def drain_step_queries() -> list[dict[str, Any]]:
  bucket = _step_queries.get()
  if bucket is None:
    return []
  return list(bucket)


def log_find(
  collection: str,
  filter_doc: dict[str, Any],
  *,
  label: str,
  source: str = "crud",
  projection: dict[str, Any] | None = None,
  sort: list[tuple[str, int]] | None = None,
  limit: int | None = None,
  latency_ms: float,
  result_count: int,
  operation: str = "find",
) -> dict[str, Any]:
  mongosh = f"db.{collection}.{operation}({_pretty(filter_doc)}"
  if projection:
    mongosh += f", {_pretty(projection)}"
  mongosh += ")"
  if sort:
    mongosh += f".sort({_pretty(sort)})"
  if limit is not None:
    mongosh += f".limit({limit})"

  return _push({
    "id": uuid.uuid4().hex[:8],
    "ts": time.time(),
    "session_id": _active_session,
    "db": _DB_NAME,
    "collection": collection,
    "operation": operation,
    "source": source,
    "label": label,
    "mongosh": mongosh,
    "filter": filter_doc,
    "projection": projection,
    "sort": sort,
    "limit": limit,
    "latency_ms": round(latency_ms, 1),
    "result_count": result_count,
  })


def log_aggregate(
  collection: str,
  pipeline: list[dict[str, Any]],
  *,
  label: str,
  source: str = "agg",
  latency_ms: float,
  result_count: int,
) -> dict[str, Any]:
  mongosh = f"db.{collection}.aggregate({_pretty(pipeline)})"
  return _push({
    "id": uuid.uuid4().hex[:8],
    "ts": time.time(),
    "session_id": _active_session,
    "db": _DB_NAME,
    "collection": collection,
    "operation": "aggregate",
    "source": source,
    "label": label,
    "mongosh": mongosh,
    "pipeline": pipeline,
    "latency_ms": round(latency_ms, 1),
    "result_count": result_count,
  })


def log_insert_one(
  collection: str,
  document: dict[str, Any],
  *,
  label: str,
  latency_ms: float,
) -> dict[str, Any]:
  mongosh = f"db.{collection}.insertOne({_pretty(document)})"
  return _push({
    "id": uuid.uuid4().hex[:8],
    "ts": time.time(),
    "session_id": _active_session,
    "db": _DB_NAME,
    "collection": collection,
    "operation": "insertOne",
    "source": "crud",
    "label": label,
    "mongosh": mongosh,
    "document": document,
    "latency_ms": round(latency_ms, 1),
    "result_count": 1,
  })


def get_recent_queries(*, limit: int = 50, session_id: str | None = None) -> list[dict[str, Any]]:
  global _log
  with _lock:
    empty = len(_log) == 0
  if empty:
    hydrated = _hydrate()
    with _lock:
      if not _log:
        _log = hydrated
  with _lock:
    entries = list(_log)

  if session_id:
    entries = [e for e in entries if e.get("session_id") == session_id]

  results = []
  for entry in entries[:limit]:
    item = dict(entry)
    ts = item.get("ts")
    if isinstance(ts, (int, float)):
      from datetime import datetime, timezone
      item["ts"] = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    results.append(item)
  return results
