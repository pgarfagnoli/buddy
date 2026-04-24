"""Idempotently merge a statusLine entry into ~/.claude/settings.json.

- Makes a timestamped backup the first time it touches the file.
- If a statusLine already points at our script, does nothing.
- If a different statusLine exists, prints a warning and bails (user must merge manually).
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path


CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"
# Tail used to recognise our statusLine no matter what Python path precedes it.
# Older installs stored `python -m …`; new installs store `<abs-path> -m …`.
STATUSLINE_MODULE_TAIL = "-m buddy.scripts.statusline"
MARKER_COMMAND = f"{sys.executable} {STATUSLINE_MODULE_TAIL}"


def main() -> int:
    CLAUDE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)

    if CLAUDE_SETTINGS.exists():
        try:
            settings = json.loads(CLAUDE_SETTINGS.read_text())
        except json.JSONDecodeError:
            print(f"error: {CLAUDE_SETTINGS} is not valid JSON; refusing to touch it", file=sys.stderr)
            return 1
    else:
        settings = {}

    existing = settings.get("statusLine")
    existing_cmd = str(existing.get("command", "")) if isinstance(existing, dict) else ""
    if existing_cmd == MARKER_COMMAND:
        print("statusLine already installed; nothing to do")
        return 0
    if STATUSLINE_MODULE_TAIL in existing_cmd:
        # Our statusLine, but with a stale Python path (or a bare `python`/
        # `python3`). Upgrade the command in place.
        backup = CLAUDE_SETTINGS.with_suffix(f".json.bak.{int(time.time())}")
        shutil.copy2(CLAUDE_SETTINGS, backup)
        print(f"backed up existing settings → {backup}")
        existing["command"] = MARKER_COMMAND
        CLAUDE_SETTINGS.write_text(json.dumps(settings, indent=2))
        print(f"upgraded statusLine interpreter path in {CLAUDE_SETTINGS}")
        return 0
    if existing:
        print(
            f"warning: a different statusLine is already configured in {CLAUDE_SETTINGS}.\n"
            f"  current: {existing}\n"
            f"  refusing to overwrite. Merge it manually by setting:\n"
            f'    "statusLine": {{"type": "command", "command": "{MARKER_COMMAND}", "refreshInterval": 5}}',
            file=sys.stderr,
        )
        return 2

    backup = CLAUDE_SETTINGS.with_suffix(f".json.bak.{int(time.time())}")
    if CLAUDE_SETTINGS.exists():
        shutil.copy2(CLAUDE_SETTINGS, backup)
        print(f"backed up existing settings → {backup}")

    settings["statusLine"] = {
        "type": "command",
        "command": MARKER_COMMAND,
        "refreshInterval": 5,
    }
    CLAUDE_SETTINGS.write_text(json.dumps(settings, indent=2))
    print(f"installed statusLine into {CLAUDE_SETTINGS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
