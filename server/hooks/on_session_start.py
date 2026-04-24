"""SessionStart hook: ensure state file exists and, on first run, nudge the
user to pick a starter. Emits stdout, which Claude Code surfaces as a system
reminder inside the session context.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

import state  # noqa: E402


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
        # stdout from a SessionStart hook is injected as a system reminder.
        print(
            "buddy is installed but no buddy has been chosen yet. "
            "If the user mentions their buddy, suggest they pick a starter — "
            "call the list_species tool, then choose_buddy with the chosen id "
            "and a name they like."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
