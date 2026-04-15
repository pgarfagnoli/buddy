"""Remove mcp-creature-bot state and reverse everything `install` did.

Mirrors `install.py`:
  1. Deregister the user-scope MCP server via the `claude` CLI
  2. Remove Stop / SessionStart / SessionEnd hooks from ~/.claude/settings.json
  3. Revert the statusLine entry
  4. Delete bundled /buddy* commands from ~/.claude/commands/ (only files that
     still match what we ship — user edits are left alone)
  5. Kill any running sidecar panes
  6. Delete the state root (~/.claude/mcp-creature-bot/)

The Python package itself stays installed — `pip uninstall mcp-creature-bot`
removes it entirely.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
from importlib import resources
from pathlib import Path

from .. import paths
from .install import COMMANDS_DIR, HOOK_EVENTS, OBSOLETE_COMMANDS
from .install_statusline import CLAUDE_SETTINGS, MARKER_COMMAND


def _kill_running_panes() -> int:
    killed = 0
    if not paths.panes_file().exists():
        return 0
    try:
        data = json.loads(paths.panes_file().read_text())
    except json.JSONDecodeError:
        return 0
    for entry in data.values():
        pid = int(entry.get("pid", 0))
        if pid > 0:
            try:
                os.kill(pid, signal.SIGTERM)
                killed += 1
            except ProcessLookupError:
                pass
            except PermissionError:
                pass
    return killed


def _remove_hooks(settings: dict) -> int:
    removed = 0
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return 0
    for event, command in HOOK_EVENTS.items():
        entries = hooks.get(event)
        if not isinstance(entries, list):
            continue
        kept = []
        for matcher in entries:
            inner = matcher.get("hooks", [])
            filtered = [
                h for h in inner
                if not (h.get("type") == "command" and h.get("command") == command)
            ]
            if len(filtered) != len(inner):
                removed += 1
            if filtered:
                matcher["hooks"] = filtered
                kept.append(matcher)
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    if not hooks:
        settings.pop("hooks", None)
    return removed


def _revert_statusline(settings: dict) -> bool:
    sl = settings.get("statusLine")
    if isinstance(sl, dict) and MARKER_COMMAND in str(sl.get("command", "")):
        settings.pop("statusLine", None)
        return True
    return False


def _update_settings() -> None:
    if not CLAUDE_SETTINGS.exists():
        return
    try:
        settings = json.loads(CLAUDE_SETTINGS.read_text())
    except json.JSONDecodeError:
        print(f"warning: {CLAUDE_SETTINGS} is not valid JSON; leaving it alone", file=sys.stderr)
        return

    removed_hooks = _remove_hooks(settings)
    reverted_statusline = _revert_statusline(settings)

    if removed_hooks or reverted_statusline:
        CLAUDE_SETTINGS.write_text(json.dumps(settings, indent=2))
    if removed_hooks:
        print(f"removed {removed_hooks} hook(s) from {CLAUDE_SETTINGS}")
    if reverted_statusline:
        print(f"removed statusLine entry from {CLAUDE_SETTINGS}")


def _remove_commands() -> int:
    if not COMMANDS_DIR.exists():
        return 0
    removed = 0
    pkg_commands = resources.files("mcp_creature_bot").joinpath("commands")
    shipped = {entry.name: entry.read_text() for entry in pkg_commands.iterdir() if entry.name.endswith(".md")}
    for name, source_text in shipped.items():
        target = COMMANDS_DIR / name
        # Check is_symlink() before exists(): a dangling symlink reports
        # exists() == False but still needs unlinking.
        if target.is_symlink():
            target.unlink()
            removed += 1
            continue
        if not target.exists():
            continue
        if target.read_text() == source_text:
            target.unlink()
            removed += 1
        else:
            print(f"  ! {name} has been edited — left alone")
    # Legacy /buddy-* files from before consolidation — delete if a distinctive
    # marker from the shipped version is still present.
    for name, marker in OBSOLETE_COMMANDS.items():
        target = COMMANDS_DIR / name
        if not target.exists():
            continue
        if marker in target.read_text():
            target.unlink()
            removed += 1
        else:
            print(f"  ! {name} has been edited — left alone")
    return removed


def _deregister_mcp_server() -> None:
    if shutil.which("claude") is None:
        print("claude CLI not found; skip `claude mcp remove --scope user mcp-creature-bot` yourself")
        return
    result = subprocess.run(
        ["claude", "mcp", "remove", "--scope", "user", "mcp-creature-bot"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("deregistered user-scope MCP server")
    else:
        stderr = result.stderr.strip()
        if "not found" in stderr.lower() or "no such" in stderr.lower():
            print("no user-scope MCP server registered (nothing to remove)")
        else:
            print(f"warning: `claude mcp remove` failed: {stderr or result.stdout.strip()}", file=sys.stderr)


def main() -> int:
    _deregister_mcp_server()
    _update_settings()

    removed_cmds = _remove_commands()
    if removed_cmds:
        print(f"removed {removed_cmds} command file(s) from {COMMANDS_DIR}")

    killed = _kill_running_panes()
    if killed:
        print(f"killed {killed} running pane(s)")

    root = paths.root()
    if root.exists():
        shutil.rmtree(root)
        print(f"removed {root}")

    print("done. Run `pip uninstall mcp-creature-bot` to remove the package itself.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
