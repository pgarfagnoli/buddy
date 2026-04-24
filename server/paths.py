"""Filesystem layout for buddy state, adapted for the Claude Code plugin.

Runtime state lives in `$CLAUDE_PLUGIN_DATA` when the plugin is active. Falls
back to `~/.claude/buddy/` for legacy installs, and performs a one-shot
migration from that path into `$CLAUDE_PLUGIN_DATA` the first time the plugin
runs alongside a pre-plugin state dir. Asset files (sprites) live at
`$CLAUDE_PLUGIN_ROOT/data/sprites/`; the fallback resolves relative to this
module's filesystem location so `python server/main.py` still works outside
Claude Code (e.g., unit tests, local CLI invocations).
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

_ROOT_ENV = "BUDDY_ROOT"
_PLUGIN_ENV = "CLAUDE_PLUGIN_DATA"
_PLUGIN_ROOT_ENV = "CLAUDE_PLUGIN_ROOT"
_LEGACY_CLAUDE_DIR_NAME = "buddy"

_MIGRATION_MARKER_NAME = "migrated-from-legacy.marker"


def root() -> Path:
    """Return the buddy state directory, creating it if missing.

    Order of precedence:
      1. `$BUDDY_ROOT` — explicit override (used in tests).
      2. `$CLAUDE_PLUGIN_DATA` — set by Claude Code when the plugin is enabled.
         On first use, we opportunistically copy `~/.claude/buddy/` into this
         dir so existing buddies survive the migration to plugin-land.
      3. `~/.claude/buddy/` — legacy path; kept as a fallback so the code
         still works if someone imports it outside a plugin context.
    """
    override = os.environ.get(_ROOT_ENV)
    if override:
        p = Path(override).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p

    plugin_data = os.environ.get(_PLUGIN_ENV)
    if plugin_data:
        p = Path(plugin_data).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        _maybe_migrate_legacy(p)
        return p

    legacy = Path.home() / ".claude" / _LEGACY_CLAUDE_DIR_NAME
    legacy.mkdir(parents=True, exist_ok=True)
    return legacy


def _maybe_migrate_legacy(plugin_root: Path) -> None:
    """One-shot copy from ~/.claude/buddy/ → $CLAUDE_PLUGIN_DATA on first run.

    Runs only if (a) we haven't already migrated (marker file absent) and
    (b) the plugin data dir doesn't already contain a state.json. Preserves
    the legacy dir as a backup — we don't delete it. Subsequent runs no-op.
    """
    marker = plugin_root / _MIGRATION_MARKER_NAME
    if marker.exists():
        return
    legacy = Path.home() / ".claude" / _LEGACY_CLAUDE_DIR_NAME
    if not legacy.is_dir():
        marker.write_text("no legacy dir; nothing to migrate\n")
        return
    if (plugin_root / "state.json").exists():
        marker.write_text("plugin dir already had state; skipped migration\n")
        return
    copied: list[str] = []
    for entry in legacy.iterdir():
        dst = plugin_root / entry.name
        if dst.exists():
            continue
        try:
            if entry.is_dir():
                shutil.copytree(entry, dst)
            else:
                shutil.copy2(entry, dst)
            copied.append(entry.name)
        except OSError:
            continue
    marker.write_text(
        "migrated from ~/.claude/buddy/; legacy dir left intact.\n"
        f"files: {', '.join(copied) or '(none)'}\n"
    )


# ─── state file paths ──────────────────────────────────────────────────────

def state_file() -> Path:
    return root() / "state.json"


def state_lock() -> Path:
    return root() / "state.lock"


def xp_log() -> Path:
    return root() / "xp.log"


def xp_log_lock() -> Path:
    return root() / "xp.log.lock"


def hooks_log() -> Path:
    return root() / "hooks.log"


def quest_log() -> Path:
    return root() / "quest.log"


# ─── plugin asset paths ────────────────────────────────────────────────────

def plugin_root() -> Path:
    """Return `$CLAUDE_PLUGIN_ROOT`, or the plugin dir inferred from this file."""
    env = os.environ.get(_PLUGIN_ROOT_ENV)
    if env:
        return Path(env).expanduser()
    # server/paths.py → plugin_root
    return Path(__file__).resolve().parent.parent


def sprites_dir() -> Path:
    return plugin_root() / "data" / "sprites"


def enemy_sprites_dir() -> Path:
    return sprites_dir() / "enemies"
