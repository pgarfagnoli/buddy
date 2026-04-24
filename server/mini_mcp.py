"""Minimal MCP stdio server. Stdlib only.

Implements just enough of the Model Context Protocol for a tool-only server:
- JSON-RPC 2.0 over newline-delimited stdio
- initialize / notifications/initialized handshake
- tools/list — advertise registered tools with their input JSON schemas
- tools/call — dispatch to handler, wrap result as MCP content

No prompts, resources, elicitation, or SSE transport. The decorator surface
mirrors `mcp.server.fastmcp.FastMCP` just enough for buddy's tool handlers to
move over with only the import line changing.
"""
from __future__ import annotations

import inspect
import json
import sys
import typing
from dataclasses import dataclass
from typing import Any, Callable


_PROTOCOL_VERSION = "2024-11-05"
_SERVER_VERSION = "0.4.0"


@dataclass
class _Tool:
    name: str
    description: str
    input_schema: dict
    fn: Callable[..., Any]


class FastMCP:
    """Drop-in subset of mcp.server.fastmcp.FastMCP for stdio tool servers."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._tools: dict[str, _Tool] = {}

    def tool(self, *, name: str | None = None, description: str | None = None):
        """Register a function as an MCP tool. Used as `@mcp.tool()`."""
        def wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or fn.__name__
            tool_desc = description or (fn.__doc__ or "").strip()
            self._tools[tool_name] = _Tool(
                name=tool_name,
                description=tool_desc,
                input_schema=_schema_from_signature(fn),
                fn=fn,
            )
            return fn
        return wrapper

    def run(self) -> None:
        """Read JSON-RPC from stdin, write to stdout, until EOF."""
        _run_stdio(self)


# ── JSON schema generation ─────────────────────────────────────────────────

_PY_TYPE_TO_JSON: dict[type, str] = {
    int: "integer",
    float: "number",
    str: "string",
    bool: "boolean",
}


def _json_type_for(hint: Any) -> dict:
    """Map a Python type hint to a JSON Schema fragment."""
    origin = typing.get_origin(hint)
    if origin is list:
        args = typing.get_args(hint)
        item_hint = args[0] if args else str
        return {"type": "array", "items": _json_type_for(item_hint)}
    if origin is dict:
        return {"type": "object"}
    if origin is typing.Union:
        # Handle Optional[T] = Union[T, None] by picking the first non-None arg.
        non_none = [a for a in typing.get_args(hint) if a is not type(None)]
        return _json_type_for(non_none[0]) if non_none else {}
    if isinstance(hint, type) and hint in _PY_TYPE_TO_JSON:
        return {"type": _PY_TYPE_TO_JSON[hint]}
    # Fallback: unknown / Any → string is the safest wire format.
    return {"type": "string"}


def _schema_from_signature(fn: Callable[..., Any]) -> dict:
    """Build an `inputSchema` object from a function's typed parameters."""
    sig = inspect.signature(fn)
    try:
        hints = typing.get_type_hints(fn)
    except NameError:
        hints = {}  # forward refs we can't resolve — fall back to str
    properties: dict[str, dict] = {}
    required: list[str] = []
    for pname, param in sig.parameters.items():
        if pname == "self":
            continue
        hint = hints.get(pname, str)
        properties[pname] = _json_type_for(hint)
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


# ── JSON-RPC envelopes ─────────────────────────────────────────────────────

def _ok(req_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id: Any, code: int, message: str, data: Any = None) -> dict:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": error}


# ── Stdio loop ─────────────────────────────────────────────────────────────

def _run_stdio(mcp: FastMCP) -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            _write(_err(None, -32700, f"parse error: {exc}"))
            continue
        response = _dispatch(mcp, msg)
        if response is not None:
            _write(response)


def _dispatch(mcp: FastMCP, msg: dict) -> dict | None:
    method = msg.get("method")
    req_id = msg.get("id")
    is_notification = req_id is None and "id" not in msg

    if method == "initialize":
        return _ok(req_id, {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": mcp.name, "version": _SERVER_VERSION},
        })
    if method == "notifications/initialized":
        return None  # notification — no response
    if method == "tools/list":
        return _ok(req_id, {
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.input_schema,
                }
                for t in mcp._tools.values()
            ]
        })
    if method == "tools/call":
        params = msg.get("params") or {}
        tool_name = params.get("name")
        tool_args = params.get("arguments") or {}
        tool = mcp._tools.get(tool_name) if tool_name else None
        if tool is None:
            return _err(req_id, -32602, f"unknown tool: {tool_name!r}")
        try:
            result = tool.fn(**tool_args)
        except Exception as exc:  # noqa: BLE001 — report any handler error as isError
            return _ok(req_id, {
                "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                "isError": True,
            })
        text = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
        return _ok(req_id, {
            "content": [{"type": "text", "text": text}],
            "isError": False,
        })

    # Unknown method — only answer if it was a request, not a notification.
    if is_notification:
        return None
    return _err(req_id, -32601, f"method not found: {method}")


def _write(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()
