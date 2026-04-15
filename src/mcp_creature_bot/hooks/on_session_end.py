"""SessionEnd hook: currently a no-op.

The buddy pane is a per-cwd singleton that outlives individual Claude Code
sessions on purpose — killing it on every session exit would make the pane
flicker in/out as you restart Claude. The user closes it explicitly via
`/buddy stop` (or by killing the tmux session).

This file stays wired up in .claude/settings.json so the hook config is stable
across releases; if we ever want per-session cleanup again, it lives here.
"""
from __future__ import annotations

import sys


def main() -> int:
    return 0


if __name__ == "__main__":
    sys.exit(main())
