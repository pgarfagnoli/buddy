"""buddy MCP server entry point.

Loads the tool registry from `tools.py` (which does `mcp = FastMCP("buddy")`
at import time and decorates each handler with `@mcp.tool()`) and runs the
stdio JSON-RPC loop via `mini_mcp`.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow bare imports (`import mini_mcp`, `import tools`, …) when this file is
# launched with its absolute path by Claude Code — the invoker's cwd is not
# guaranteed to be the server directory.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import tools  # noqa: E402 — triggers @mcp.tool() registrations


def main() -> None:
    tools.mcp.run()


if __name__ == "__main__":
    main()
