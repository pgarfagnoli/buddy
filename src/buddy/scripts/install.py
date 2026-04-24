"""Install buddy as a user-scope Claude Code integration.

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

from .install_statusline import (
    CLAUDE_SETTINGS,
    MARKER_COMMAND as STATUSLINE_COMMAND,
    STATUSLINE_MODULE_TAIL,
)


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

# Each hook command is pinned to `sys.executable` at install time so it keeps
# working even when Claude Code spawns the hook from a shell whose PATH resolves
# `python3` to a different interpreter (e.g. python@3.14) that doesn't have the
# buddy package installed.
HOOK_EVENTS = {
    "Stop":         f"{sys.executable} -m buddy.hooks.on_stop",
    "SessionStart": f"{sys.executable} -m buddy.hooks.on_session_start",
    "SessionEnd":   f"{sys.executable} -m buddy.hooks.on_session_end",
}

HOOK_MARKER = "buddy.hooks."
# Pre-rename markers: older installs wired everything to the mcp_creature_bot
# module. We strip/upgrade those during install so the rename is seamless.
LEGACY_HOOK_MARKER = "mcp_creature_bot.hooks."
LEGACY_STATUSLINE_MARKER = "mcp_creature_bot.scripts.statusline"
LEGACY_MCP_SERVER_NAME = "mcp-creature-bot"


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
    pkg_commands = resources.files("buddy").joinpath("commands")
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
            # Stale symlinks from earlier installs: either broken (target is
            # gone) or still pointing at the pre-rename mcp_creature_bot path.
            # Treat those as ours and upgrade in place; anything else is a
            # user-directed symlink and we leave it alone.
            link_target = os.readlink(target)
            resolved_exists = target.exists()
            if not resolved_exists or "mcp_creature_bot" in link_target:
                target.unlink()
                target.symlink_to(source_path)
                migrated += 1
                continue
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


def _strip_legacy_hooks(settings: dict) -> int:
    """Remove hook entries that point at the pre-rename mcp_creature_bot module.

    Returns the number of hook command entries pruned. Empty matcher entries
    (those whose only hooks were legacy) are also removed.
    """
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return 0
    pruned = 0
    for event, entries in list(hooks.items()):
        if not isinstance(entries, list):
            continue
        new_entries: list = []
        for matcher in entries:
            if not isinstance(matcher, dict):
                new_entries.append(matcher)
                continue
            kept_hooks = []
            for hook in matcher.get("hooks", []):
                cmd = hook.get("command", "") if isinstance(hook, dict) else ""
                if LEGACY_HOOK_MARKER in cmd:
                    pruned += 1
                    continue
                kept_hooks.append(hook)
            if kept_hooks:
                matcher["hooks"] = kept_hooks
                new_entries.append(matcher)
        if new_entries:
            hooks[event] = new_entries
        else:
            del hooks[event]
    return pruned


def _strip_stale_buddy_hooks(settings: dict) -> int:
    """Remove `buddy.hooks.*` entries whose command doesn't match the current
    `HOOK_EVENTS` value for that event. Lets re-runs upgrade the baked-in
    Python path (e.g. an older install that hard-coded `python3`)."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return 0
    pruned = 0
    for event, entries in list(hooks.items()):
        if not isinstance(entries, list):
            continue
        expected = HOOK_EVENTS.get(event)
        new_entries: list = []
        for matcher in entries:
            if not isinstance(matcher, dict):
                new_entries.append(matcher)
                continue
            kept_hooks = []
            for hook in matcher.get("hooks", []):
                cmd = hook.get("command", "") if isinstance(hook, dict) else ""
                if HOOK_MARKER in cmd and cmd != expected:
                    pruned += 1
                    continue
                kept_hooks.append(hook)
            if kept_hooks:
                matcher["hooks"] = kept_hooks
                new_entries.append(matcher)
        if new_entries:
            hooks[event] = new_entries
        else:
            del hooks[event]
    return pruned


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
    """Returns 'installed', 'already-installed', 'upgraded', or 'conflict'."""
    existing = settings.get("statusLine")
    existing_cmd = str(existing.get("command", "")) if isinstance(existing, dict) else ""
    if isinstance(existing, dict) and existing_cmd == STATUSLINE_COMMAND:
        return "already-installed"
    if isinstance(existing, dict) and STATUSLINE_MODULE_TAIL in existing_cmd:
        # Our statusLine, but the stored command uses a stale Python path
        # (e.g. bare `python` from v0.3.3). Upgrade the interpreter in place.
        existing["command"] = STATUSLINE_COMMAND
        return "upgraded"
    if isinstance(existing, dict) and LEGACY_STATUSLINE_MARKER in existing_cmd:
        # Pre-rename statusLine still in settings.json — the old module is gone
        # so leaving it would break every tick. Upgrade it in place.
        settings["statusLine"] = {
            "type": "command",
            "command": STATUSLINE_COMMAND,
            "refreshInterval": 5,
        }
        return "upgraded"
    if existing:
        return "conflict"
    settings["statusLine"] = {
        "type": "command",
        "command": STATUSLINE_COMMAND,
        "refreshInterval": 5,
    }
    return "installed"


def _deregister_legacy_mcp_server() -> None:
    """Remove the pre-rename `mcp-creature-bot` user-scope MCP server, if present."""
    if shutil.which("claude") is None:
        return
    check = subprocess.run(
        ["claude", "mcp", "list"],
        capture_output=True,
        text=True,
    )
    if check.returncode != 0 or LEGACY_MCP_SERVER_NAME not in check.stdout:
        return
    subprocess.run(
        ["claude", "mcp", "remove", "--scope", "user", LEGACY_MCP_SERVER_NAME],
        capture_output=True,
        text=True,
    )
    print(f"  removed legacy MCP server registration: {LEGACY_MCP_SERVER_NAME}")


def _register_mcp_server() -> str:
    """Register buddy as a user-scope MCP server via the `claude` CLI.

    Always removes any existing `buddy` registration first so re-runs upgrade
    the stored command (older installs baked `python3` into it; we now bake
    `sys.executable`). Returns a short status string for the summary line.
    """
    if shutil.which("claude") is None:
        return (
            "WARNING — claude CLI not found on PATH; MCP server NOT registered.\n"
            "    Install Claude Code, then re-run `buddy-install` to finish wiring this up.\n"
            "    (Or register manually:"
            f" claude mcp add --scope user buddy -- {sys.executable} -m buddy.server)"
        )

    check = subprocess.run(
        ["claude", "mcp", "list"],
        capture_output=True,
        text=True,
    )
    # `.split()` avoids matching `buddy` as a substring of something else.
    had_prior = check.returncode == 0 and "buddy" in check.stdout.split()
    if had_prior:
        subprocess.run(
            ["claude", "mcp", "remove", "--scope", "user", "buddy"],
            capture_output=True,
            text=True,
        )

    result = subprocess.run(
        [
            "claude", "mcp", "add",
            "--scope", "user",
            "buddy",
            "--",
            sys.executable, "-m", "buddy.server",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return f"FAILED: {result.stderr.strip() or result.stdout.strip()}"
    return "re-registered (user scope)" if had_prior else "registered at user scope"


def main() -> int:
    print("installing buddy…")

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

    pruned = _strip_legacy_hooks(settings)
    if pruned:
        print(f"  legacy hooks: pruned {pruned} stale mcp_creature_bot entries")

    stale = _strip_stale_buddy_hooks(settings)
    if stale:
        print(f"  hooks: pruned {stale} stale entry/entries (upgrading interpreter path)")

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
    elif statusline_status == "upgraded":
        print("  statusLine: upgraded stale mcp_creature_bot entry to buddy")
    else:
        print(
            f"  statusLine: CONFLICT — a different statusLine is set in {CLAUDE_SETTINGS}; left it alone.\n"
            f"    merge it manually: \"statusLine\": {{\"type\": \"command\", \"command\": \"{STATUSLINE_COMMAND}\", \"refreshInterval\": 5}}",
            file=sys.stderr,
        )

    # 3. MCP server registration (and clean up the old name if present)
    _deregister_legacy_mcp_server()
    print(f"  mcp server: {_register_mcp_server()}")

    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
