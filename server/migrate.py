"""One-shot migration from pre-v0.4.0 Homebrew/pip installs.

v0.3.x buddy ran an imperative `buddy-install` CLI that hand-patched
`~/.claude/settings.json` with hooks + statusLine + a user-scope MCP
registration, and dropped `/buddy*` slash-command files into
`~/.claude/commands/`. v0.4.0 (plugin) declares all of those via its own
manifests — the old entries become dead weight and fire
`ModuleNotFoundError: No module named 'buddy'` on every turn because the
pip package is gone.

This module detects and cleans up those artifacts. It's invoked on-demand
via the `/buddy:migrate` skill, which calls the `run_migration` MCP tool.
Idempotent — the marker file in `$CLAUDE_PLUGIN_DATA` tells it not to
rerun.

Settings.json is backed up with a timestamped suffix before any mutation.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import paths


_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
_COMMANDS_DIR = Path.home() / ".claude" / "commands"
_MARKER_NAME = "migrated-v0.4.0.marker"

# Substrings that identify a buddy-flavored hook or statusLine command.
_LEGACY_HOOK_MARKERS = ("buddy.hooks.", "mcp_creature_bot.hooks.")
_LEGACY_STATUSLINE_MARKERS = (
    "buddy.scripts.statusline",
    "mcp_creature_bot.scripts.statusline",
)

# User-scope MCP server names v0.3.x might have registered.
_LEGACY_MCP_NAMES = ("buddy", "mcp-creature-bot")

# Distinctive `description:` lines v0.3.x (and earlier) shipped in
# ~/.claude/commands/*.md. If a user's file still contains one of these, we
# treat it as ours and delete; anything they edited away is left alone.
_SHIPPED_COMMAND_MARKERS: dict[str, list[str]] = {
    "buddy.md": [
        "description: Interact with your RPG buddy",
        "description: Show your RPG buddy's current status",
    ],
    "buddy-start.md":     ["description: Launch the buddy sidecar pane"],
    "buddy-stop.md":      ["description: Close the buddy sidecar pane"],
    "buddy-allocate.md":  ["description: Spend your buddy's unallocated stat points"],
    "buddy-quest.md":     ["description: Send your buddy on a quest"],
    "buddy-claim.md":     ["description: Claim rewards from a completed quest"],
    "buddy-rename.md":    ["description: Rename your buddy"],
    "buddy-uninstall.md": [
        "description: Remove mcp-creature-bot state",
        "description: Remove buddy state",
    ],
}


# ─── public API ────────────────────────────────────────────────────────────

def marker_path() -> Path:
    return paths.root() / _MARKER_NAME


def is_migration_needed() -> bool:
    """Fast check for SessionStart. True iff the marker is missing AND there's
    something actually worth cleaning up. Runs a shell-out to `claude mcp list`
    only if the other, cheaper checks don't already surface artifacts."""
    if marker_path().exists():
        return False
    report = _detect_artifacts(include_mcp=False)
    if _has_findings(report):
        return True
    # Only pay the subprocess cost when the cheap signals came up empty.
    return bool(_detect_mcp_servers())


def detect_legacy_artifacts() -> dict[str, Any]:
    """Full survey. Read-only; safe to call for a dry-run."""
    return _detect_artifacts(include_mcp=True)


def run_legacy_migration(dry_run: bool = False) -> dict[str, Any]:
    """Detect + (optionally) clean up pre-v0.4.0 buddy artifacts.

    On success writes a marker to `$CLAUDE_PLUGIN_DATA` so subsequent calls
    are no-ops. Returns a structured report.
    """
    if marker_path().exists() and not dry_run:
        return {
            "status": "already-migrated",
            "marker": str(marker_path()),
            "marker_contents": marker_path().read_text(errors="replace").strip(),
        }

    report = _detect_artifacts(include_mcp=True)
    report["dry_run"] = bool(dry_run)
    findings = _has_findings(report)

    if not findings:
        report["status"] = "nothing-to-do"
        if not dry_run:
            marker_path().write_text(
                f"migrated at {int(time.time())}; no legacy artifacts found\n"
            )
        return report

    if dry_run:
        report["status"] = "would-migrate"
        return report

    # Backup settings.json once, before any mutation.
    if _SETTINGS_PATH.exists():
        ts = int(time.time())
        backup = _SETTINGS_PATH.with_suffix(f".json.bak.{ts}.pre-v0.4.0-migrate")
        try:
            shutil.copy2(_SETTINGS_PATH, backup)
            report["settings_backup"] = str(backup)
        except OSError as exc:
            report["settings_backup_error"] = str(exc)

    # Mutate settings.json.
    settings = _load_settings() or {}
    _strip_legacy_hooks(settings)
    _strip_legacy_statusline(settings)
    _save_settings(settings)

    # Remove user-scope MCP registration(s).
    removed_mcp: list[str] = []
    for name in report["legacy_mcp_servers"]:
        if _remove_mcp_user_scope(name):
            removed_mcp.append(name)
    report["removed_mcp_servers"] = removed_mcp

    # Delete shipped command files.
    deleted: list[str] = []
    for fname in report["legacy_commands"]:
        p = _COMMANDS_DIR / fname
        try:
            p.unlink()
            deleted.append(fname)
        except OSError:
            continue
    report["deleted_commands"] = deleted

    # Record what happened so the next session doesn't re-nudge.
    marker_path().write_text(
        f"migrated at {int(time.time())}\n"
        f"hooks stripped: {len(report['legacy_hooks'])}\n"
        f"statusline stripped: {bool(report.get('legacy_statusline'))}\n"
        f"mcp servers removed: {', '.join(removed_mcp) or '(none)'}\n"
        f"commands deleted: {', '.join(deleted) or '(none)'}\n"
    )
    report["status"] = "migrated"
    return report


# ─── detection ─────────────────────────────────────────────────────────────

def _detect_artifacts(include_mcp: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "legacy_hooks": [],
        "legacy_statusline": None,
        "legacy_mcp_servers": [],
        "legacy_commands": [],
    }
    settings = _load_settings()
    if settings:
        hooks = settings.get("hooks")
        if isinstance(hooks, dict):
            for event, entries in hooks.items():
                if not isinstance(entries, list):
                    continue
                for matcher in entries:
                    if not isinstance(matcher, dict):
                        continue
                    for h in matcher.get("hooks", []) or []:
                        if not isinstance(h, dict):
                            continue
                        cmd = str(h.get("command", ""))
                        if _contains_any(cmd, _LEGACY_HOOK_MARKERS):
                            report["legacy_hooks"].append(
                                {"event": event, "command": cmd}
                            )
        statusline = settings.get("statusLine")
        if isinstance(statusline, dict):
            cmd = str(statusline.get("command", ""))
            if _contains_any(cmd, _LEGACY_STATUSLINE_MARKERS):
                report["legacy_statusline"] = cmd

    if include_mcp:
        report["legacy_mcp_servers"] = _detect_mcp_servers()

    if _COMMANDS_DIR.is_dir():
        for fname, markers in _SHIPPED_COMMAND_MARKERS.items():
            p = _COMMANDS_DIR / fname
            if not p.exists():
                continue
            try:
                content = p.read_text()
            except OSError:
                continue
            if any(m in content for m in markers):
                report["legacy_commands"].append(fname)

    return report


def _has_findings(report: dict[str, Any]) -> bool:
    return bool(
        report.get("legacy_hooks")
        or report.get("legacy_statusline")
        or report.get("legacy_mcp_servers")
        or report.get("legacy_commands")
    )


def _detect_mcp_servers() -> list[str]:
    """Return names of user-scope MCP servers that look like pre-v0.4.0 buddy."""
    claude = shutil.which("claude")
    if not claude:
        return []
    try:
        r = subprocess.run(
            [claude, "mcp", "list"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if r.returncode != 0:
        return []
    found: list[str] = []
    for line in r.stdout.splitlines():
        # Example line: "buddy: python3 -m buddy.server - ✗ Failed to connect"
        for name in _LEGACY_MCP_NAMES:
            if line.startswith(name + ":") or line.startswith(name + " "):
                if "buddy.server" in line or "mcp_creature_bot.server" in line:
                    if name not in found:
                        found.append(name)
    return found


# ─── mutation helpers ──────────────────────────────────────────────────────

def _load_settings() -> dict | None:
    if not _SETTINGS_PATH.exists():
        return None
    try:
        return json.loads(_SETTINGS_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _save_settings(settings: dict) -> None:
    tmp = _SETTINGS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(settings, indent=2))
    os.rename(tmp, _SETTINGS_PATH)


def _strip_legacy_hooks(settings: dict) -> int:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return 0
    pruned = 0
    for event in list(hooks.keys()):
        entries = hooks[event]
        if not isinstance(entries, list):
            continue
        new_entries = []
        for matcher in entries:
            if not isinstance(matcher, dict):
                new_entries.append(matcher)
                continue
            kept = []
            for h in matcher.get("hooks", []) or []:
                cmd = h.get("command", "") if isinstance(h, dict) else ""
                if _contains_any(cmd, _LEGACY_HOOK_MARKERS):
                    pruned += 1
                    continue
                kept.append(h)
            if kept:
                matcher["hooks"] = kept
                new_entries.append(matcher)
        if new_entries:
            hooks[event] = new_entries
        else:
            del hooks[event]
    if not hooks:
        del settings["hooks"]
    return pruned


def _strip_legacy_statusline(settings: dict) -> bool:
    sl = settings.get("statusLine")
    if not isinstance(sl, dict):
        return False
    cmd = str(sl.get("command", ""))
    if _contains_any(cmd, _LEGACY_STATUSLINE_MARKERS):
        del settings["statusLine"]
        return True
    return False


def _remove_mcp_user_scope(name: str) -> bool:
    claude = shutil.which("claude")
    if not claude:
        return False
    try:
        r = subprocess.run(
            [claude, "mcp", "remove", "--scope", "user", name],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


def _contains_any(haystack: str, needles: tuple[str, ...]) -> bool:
    return any(n in haystack for n in needles)
