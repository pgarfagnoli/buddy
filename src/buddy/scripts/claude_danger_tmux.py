"""Launch `claude --dangerously-skip-permissions` inside a fresh tmux session."""
from __future__ import annotations

import os
import shutil
import sys
import time


def main() -> int:
    if shutil.which("tmux") is None:
        print("claude-danger-tmux: tmux not found on PATH", file=sys.stderr)
        return 1
    if shutil.which("claude") is None:
        print("claude-danger-tmux: `claude` CLI not found on PATH", file=sys.stderr)
        return 1
    session = f"claude-danger-{int(time.time())}"
    extra = sys.argv[1:]
    os.execvp(
        "tmux",
        [
            "tmux", "new-session", "-s", session,
            "claude", "--dangerously-skip-permissions", *extra,
        ],
    )


if __name__ == "__main__":
    sys.exit(main())
