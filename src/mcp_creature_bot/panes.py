"""Per-tmux-window sidecar pane registry.

One pane per tmux window running a Claude Code session. Two Claude
sessions in different tmux sessions (or different windows of the same
session) each get their own live pane; all of them render the same
shared buddy state. A fresh `start_pane` call for a window that already
has a live pane is a no-op.
"""
from __future__ import annotations

import fcntl
import json
import os
import signal
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from . import paths


@contextmanager
def _lock() -> Iterator[None]:
    lock_path = paths.panes_lock()
    lock_path.touch(exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _load() -> dict[str, Any]:
    p = paths.panes_file()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}


def _save(data: dict[str, Any]) -> None:
    p = paths.panes_file()
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.rename(tmp, p)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def get_live_entry(window_id: str) -> Optional[dict[str, Any]]:
    """Return the live pane entry for this tmux window, or None if missing/dead."""
    data = _load()
    entry = data.get(window_id)
    if not entry:
        return None
    if not _pid_alive(int(entry.get("pid", 0))):
        return None
    return entry


def register(window_id: str, pid: int, pane_id: str, cwd: str) -> None:
    """Register a newly-spawned pane keyed by tmux window id.

    Sweeps two kinds of cruft while holding the lock:
      1. Entries whose pid is dead (ordinary cleanup).
      2. Legacy per-cwd entries (keys not starting with '@') — those
         pre-date the window-id schema. We SIGTERM their pane process
         so the user doesn't end up with an unmanaged zombie pane in
         some other window after upgrade.
    """
    with _lock():
        data = _load()
        to_drop: list[str] = []
        for k, v in data.items():
            pid_v = int(v.get("pid", 0))
            if not _pid_alive(pid_v):
                to_drop.append(k)
                continue
            if not k.startswith("@"):
                try:
                    os.kill(pid_v, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                to_drop.append(k)
        for k in to_drop:
            data.pop(k, None)
        data[window_id] = {"pid": pid, "pane_id": pane_id, "cwd": cwd}
        _save(data)


def unregister(window_id: str) -> None:
    """Remove the pane entry for this tmux window, if any."""
    with _lock():
        data = _load()
        if data.pop(window_id, None) is not None:
            _save(data)
