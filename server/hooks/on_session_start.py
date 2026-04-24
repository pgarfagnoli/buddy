"""Stub SessionStart hook. Touches a marker file in CLAUDE_PLUGIN_DATA so we
can verify the plugin's hook wiring fires without any XP/state logic yet."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def main() -> int:
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data_dir:
        # Fallback for dev mode / missing env
        data_dir = str(Path.home() / ".claude" / "plugins" / "data" / "buddy-dev")
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    (Path(data_dir) / "session_start.marker").write_text(
        f"session_start fired at {int(time.time())}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
