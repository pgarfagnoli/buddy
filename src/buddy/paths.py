"""Filesystem layout for buddy state."""
from __future__ import annotations

import os
from pathlib import Path

_ROOT_ENV = "BUDDY_ROOT"
_LEGACY_DIR_NAME = "mcp-creature-bot"
_CURRENT_DIR_NAME = "buddy"


def root() -> Path:
    override = os.environ.get(_ROOT_ENV)
    if override:
        p = Path(override).expanduser()
    else:
        claude = Path.home() / ".claude"
        new = claude / _CURRENT_DIR_NAME
        legacy = claude / _LEGACY_DIR_NAME
        if not new.exists() and legacy.exists():
            # One-time migration from the pre-rename state dir.
            legacy.rename(new)
        p = new
    p.mkdir(parents=True, exist_ok=True)
    return p


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


def activity_loop_lock() -> Path:
    return root() / "activity_loop.lock"


def activity_loop_pid() -> Path:
    return root() / "activity_loop.pid"


def activity_loop_log() -> Path:
    return root() / "activity_loop.log"


def panes_file() -> Path:
    return root() / "panes.json"


def panes_lock() -> Path:
    return root() / "panes.lock"


def quest_log() -> Path:
    return root() / "quest.log"
