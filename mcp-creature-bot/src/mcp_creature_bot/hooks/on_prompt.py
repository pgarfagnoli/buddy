"""UserPromptSubmit hook: sub-ms XP event append.

Reads JSON from stdin, appends one line to xp.log, exits 0 with no stdout.
No state reads, no lock contention. Must stay trivial.
"""
from __future__ import annotations

import json
import sys
import time

from .. import state


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0  # never block the user's prompt over a hook parse error
    prompt = payload.get("prompt") or ""
    session = payload.get("session_id") or ""
    try:
        state.append_xp_event({
            "t": int(time.time()),
            "session": session,
            "prompt_len": len(prompt),
        })
    except Exception:
        # Never block the prompt. Drop the event silently.
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
