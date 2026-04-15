"""Install mcp-creature-bot as a user-scope Claude Code integration.

Idempotent. Running it twice in a row is a no-op the second time.

Does four things:
  1. Symlinks bundled /buddy slash command into ~/.claude/commands/
  2. Merges Stop / SessionStart / SessionEnd hooks into ~/.claude/settings.json
  3. Installs the statusLine entry (via install_statusline)
  4. Registers the MCP server at user scope via the `claude` CLI
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from importlib import resources
from pathlib import Path

from .install_statusline import CLAUDE_SETTINGS, MARKER_COMMAND as STATUSLINE_COMMAND


COMMANDS_DIR = Path.home() / ".claude" / "commands"

# Legacy command files from before `/buddy` was consolidated into a single
# dispatcher. Keys are filenames we used to ship; values are a distinctive
# frontmatter `description:` line from the shipped version. On install we
# delete a legacy file only if that marker is still present — user edits that
# rewrote the description are left alone.
OBSOLETE_COMMANDS: dict[str, str] = {
    "buddy-start.md":     "description: Launch the buddy sidecar pane in the current tmux window.",
    "buddy-stop.md":      "description: Close the buddy sidecar pane for this working directory.",
    "buddy-allocate.md":  "description: Spend your buddy's unallocated stat points.",
    "buddy-quest.md":     "description: Send your buddy on a quest, or list available quests.",
    "buddy-claim.md":     "description: Claim rewards from a completed quest.",
    "buddy-rename.md":    "description: Rename your buddy.",
    "buddy-uninstall.md": "description: Remove mcp-creature-bot state, kill panes, revert statusLine.",
}

# Distinctive marker strings for earlier shipped versions of files that we
# STILL ship (just with different content). If the installed file contains
# any of these markers we treat it as our own old version and auto-upgrade
# (replace with a fresh symlink). User edits that rewrote the description
# won't match and will be left alone as conflicts.
LEGACY_SHIPPED_MARKERS: dict[str, list[str]] = {
    "buddy.md": [
        "description: Show your RPG buddy's current status (level, HP, XP, stats, active quest).",
    ],
}

HOOK_EVENTS = {
    "Stop": "python3 -m mcp_creature_bot.hooks.on_stop",
    "SessionStart": "python3 -m mcp_creature_bot.hooks.on_session_start",
    "SessionEnd": "python3 -m mcp_creature_bot.hooks.on_session_end",
}

HOOK_MARKER = "mcp_creature_bot.hooks."


def _backup_settings() -> None:
    if not CLAUDE_SETTINGS.exists():
        return
    backup = CLAUDE_SETTINGS.with_suffix(f".json.bak.{int(time.time())}")
    shutil.copy2(CLAUDE_SETTINGS, backup)
    print(f"backed up existing settings → {backup}")


def _load_settings() -> dict:
    if not CLAUDE_SETTINGS.exists():
        return {}
    try:
        return json.loads(CLAUDE_SETTINGS.read_text())
    except json.JSONDecodeError:
        print(f"error: {CLAUDE_SETTINGS} is not valid JSON; refusing to touch it", file=sys.stderr)
        sys.exit(1)


def _resolve_source_path(entry) -> Path | None:
    """Real filesystem path of a package-resources entry, or None if it lives
    in a zipimport/egg and has no persistent path we can symlink to."""
    try:
        p = Path(os.fspath(entry))
    except (TypeError, NotImplementedError):
        return None
    return p if p.exists() else None


def _link_commands() -> tuple[int, int, int, list[str]]:
    """Symlink bundled /buddy command file(s) into COMMANDS_DIR.

    Returns (linked, migrated, skipped, conflicts). `linked` counts fresh
    symlinks, `migrated` counts old-style copies that were replaced with a
    symlink, `skipped` counts files already correctly linked, and `conflicts`
    lists user-edited files we left alone.

    Falls back to copying on Windows (symlinks need admin/dev mode) and on
    zipimport'd packages (source has no filesystem path).
    """
    COMMANDS_DIR.mkdir(parents=True, exist_ok=True)
    linked = 0
    migrated = 0
    skipped = 0
    conflicts: list[str] = []
    use_copy_fallback = os.name == "nt"
    pkg_commands = resources.files("mcp_creature_bot").joinpath("commands")
    for entry in pkg_commands.iterdir():
        if not entry.name.endswith(".md"):
            continue
        target = COMMANDS_DIR / entry.name
        source_path = _resolve_source_path(entry)

        if source_path is None or use_copy_fallback:
            # Copy fallback — preserves legacy behavior for this one file.
            source_text = entry.read_text()
            if target.is_symlink() or target.exists():
                existing = target.read_text() if target.exists() else ""
                if existing == source_text:
                    skipped += 1
                    continue
                conflicts.append(entry.name)
                continue
            target.write_text(source_text)
            linked += 1
            continue

        if target.is_symlink():
            try:
                if target.resolve() == source_path.resolve():
                    skipped += 1
                    continue
            except OSError:
                pass
            # Symlink points somewhere else — user-directed, leave alone.
            conflicts.append(entry.name)
            continue

        if target.exists():
            existing_text = target.read_text()
            shipped_text = source_path.read_text()
            is_current_shipped = existing_text == shipped_text
            is_legacy_shipped = any(
                marker in existing_text
                for marker in LEGACY_SHIPPED_MARKERS.get(entry.name, [])
            )
            if is_current_shipped or is_legacy_shipped:
                target.unlink()
                target.symlink_to(source_path)
                migrated += 1
            else:
                conflicts.append(entry.name)
            continue

        target.symlink_to(source_path)
        linked += 1

    return linked, migrated, skipped, conflicts


def _remove_obsolete_commands() -> tuple[int, list[str]]:
    """Delete legacy /buddy-* command files left over from before consolidation."""
    removed = 0
    conflicts: list[str] = []
    if not COMMANDS_DIR.exists():
        return 0, []
    for name, marker in OBSOLETE_COMMANDS.items():
        target = COMMANDS_DIR / name
        if not target.exists():
            continue
        if marker in target.read_text():
            target.unlink()
            removed += 1
        else:
            conflicts.append(name)
    return removed, conflicts


def _hook_command_present(event_entries: list, command: str) -> bool:
    for matcher in event_entries:
        for hook in matcher.get("hooks", []):
            if hook.get("type") == "command" and hook.get("command") == command:
                return True
    return False


def _merge_hooks(settings: dict) -> int:
    added = 0
    hooks = settings.setdefault("hooks", {})
    for event, command in HOOK_EVENTS.items():
        entries = hooks.setdefault(event, [])
        if _hook_command_present(entries, command):
            continue
        entries.append({"hooks": [{"type": "command", "command": command}]})
        added += 1
    return added


def _merge_statusline(settings: dict) -> str:
    """Returns 'installed', 'already-installed', or 'conflict'."""
    existing = settings.get("statusLine")
    if isinstance(existing, dict) and STATUSLINE_COMMAND in str(existing.get("command", "")):
        return "already-installed"
    if existing:
        return "conflict"
    settings["statusLine"] = {
        "type": "command",
        "command": STATUSLINE_COMMAND,
        "refreshInterval": 5,
    }
    return "installed"


def _register_mcp_server() -> str:
    """Register mcp-creature-bot as a user-scope MCP server via the `claude` CLI.

    Returns a short status string for the summary line.
    """
    if shutil.which("claude") is None:
        return (
            "claude CLI not found on PATH — skipped. Run this yourself:\n"
            "    claude mcp add --scope user mcp-creature-bot -- python3 -m mcp_creature_bot.server"
        )

    check = subprocess.run(
        ["claude", "mcp", "list"],
        capture_output=True,
        text=True,
    )
    if check.returncode == 0 and "mcp-creature-bot" in check.stdout:
        return "already registered (user scope)"

    result = subprocess.run(
        [
            "claude", "mcp", "add",
            "--scope", "user",
            "mcp-creature-bot",
            "--",
            "python3", "-m", "mcp_creature_bot.server",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return f"FAILED: {result.stderr.strip() or result.stdout.strip()}"
    return "registered at user scope"


def main() -> int:
    print("installing mcp-creature-bot…")

    # 1. Commands
    linked, migrated, skipped, conflicts = _link_commands()
    print(
        f"  commands: {linked} linked, {migrated} migrated from copy, "
        f"{skipped} already up-to-date"
    )
    for name in conflicts:
        print(f"    ! {name} exists with different content — left alone")

    removed_legacy, legacy_conflicts = _remove_obsolete_commands()
    if removed_legacy:
        print(f"  legacy commands: removed {removed_legacy} obsolete file(s)")
    for name in legacy_conflicts:
        print(f"    ! {name} has been edited — left alone")

    # 2. Hooks + statusLine: load settings once, mutate, write once, back up once.
    CLAUDE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    settings = _load_settings()
    before = json.dumps(settings, sort_keys=True)

    added = _merge_hooks(settings)
    statusline_status = _merge_statusline(settings)

    after = json.dumps(settings, sort_keys=True)
    if before != after:
        _backup_settings()
        CLAUDE_SETTINGS.write_text(json.dumps(settings, indent=2))

    if added:
        print(f"  hooks: {added} added to {CLAUDE_SETTINGS}")
    else:
        print("  hooks: already installed")

    if statusline_status == "installed":
        print(f"  statusLine: installed into {CLAUDE_SETTINGS}")
    elif statusline_status == "already-installed":
        print("  statusLine: already installed")
    else:
        print(
            f"  statusLine: CONFLICT — a different statusLine is set in {CLAUDE_SETTINGS}; left it alone.\n"
            f"    merge it manually: \"statusLine\": {{\"type\": \"command\", \"command\": \"{STATUSLINE_COMMAND}\", \"refreshInterval\": 5}}",
            file=sys.stderr,
        )

    # 3. MCP server registration
    print(f"  mcp server: {_register_mcp_server()}")

    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
