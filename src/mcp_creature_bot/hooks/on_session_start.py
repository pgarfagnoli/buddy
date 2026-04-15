"""SessionStart hook: ensure state file exists and, on first run, nudge the user.

Never spawns a tmux pane — that's `/buddy start`'s job, which runs in the user's
shell context where $TMUX is reliably set.
"""
from __future__ import annotations

import json
import sys

from .. import state


def main() -> int:
    try:
        _ = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        pass
    try:
        state.init_state_if_missing()
        s = state.load_state()
    except Exception:
        return 0
    if s.buddy is None:
        # Non-JSON stdout is injected into Claude's context as a system reminder.
        print(
            "mcp-creature-bot is installed but no buddy has been chosen yet. "
            "If the user mentions the buddy, suggest they pick a starter "
            "(call the list_species tool, then choose_buddy) and run /buddy "
            "inside tmux to launch the sidecar pane."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
