"""buddy MCP server entry point.

Walking-skeleton edition: registers a single stub tool so we can prove the
plugin → MCP → stdio round-trip works end to end before porting the real
game logic in `src/buddy/server.py` over.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow `import mini_mcp` when launched as `python3 server/main.py` regardless
# of the user's cwd. Claude Code invokes this with an absolute path.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from mini_mcp import FastMCP  # noqa: E402


mcp = FastMCP("buddy")


@mcp.tool()
def get_buddy() -> dict:
    """Stub: returns a placeholder buddy state so the plugin flow can be
    verified. Real tools land in phase 2 of the rewrite."""
    return {
        "buddy": None,
        "note": "walking skeleton — real tools pending",
        "skeleton_version": "0.4.0-dev",
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
