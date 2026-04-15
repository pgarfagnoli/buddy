"""Filesystem layout for mcp-creature-bot state."""
from __future__ import annotations

import os
from pathlib import Path

_ROOT_ENV = "MCP_CREATURE_BOT_ROOT"


def root() -> Path:
    override = os.environ.get(_ROOT_ENV)
    if override:
        p = Path(override).expanduser()
    else:
        p = Path.home() / ".claude" / "mcp-creature-bot"
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
