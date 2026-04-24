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
import migrate  # noqa: E402


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

    # If the user upgraded from the Homebrew/pip era, their settings.json and
    # ~/.claude/commands/ may still carry pre-v0.4.0 buddy entries. Nudge them
    # to run /buddy:migrate — exactly once. The nudge goes to stdout, which
    # Claude Code injects as a system reminder.
    try:
        if migrate.is_migration_needed():
            print(
                "buddy plugin: pre-v0.4.0 artifacts detected in ~/.claude/ "
                "(likely leftover hooks, statusLine, MCP registration, or "
                "/buddy* command files from a previous Homebrew install). "
                "Suggest the user run /buddy:migrate — it backs up settings.json "
                "and strips the stale entries."
            )
    except Exception:
        pass

    if s.buddy is None:
        print(
            "buddy is installed but no buddy has been chosen yet. "
            "If the user mentions their buddy, suggest they pick a starter — "
            "call the list_species tool, then choose_buddy with the chosen id "
            "and a name they like."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
