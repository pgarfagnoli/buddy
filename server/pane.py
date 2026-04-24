"""Standalone buddy-pane renderer.

Reads buddy state from whichever plugin-data dir is active and repaints a
compact status view on a ~2s interval. Designed to run in any terminal —
a Terminal.app window, an iTerm split, a tmux pane, wezterm, kitty, etc.
No tmux-specific code here. Ctrl-C to quit.

State-dir resolution (first match wins):
  1. $BUDDY_ROOT override (useful for tests).
  2. $CLAUDE_PLUGIN_DATA if the user exports it.
  3. Scan ~/.claude/plugins/data/* for a child dir containing state.json.
     Prefer a path whose basename contains "buddy" if multiple match.
  4. Legacy ~/.claude/buddy/state.json.
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional


REFRESH_SECONDS = 2.0
CLEAR_SCREEN = "\x1b[2J\x1b[H"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
BAR_WIDTH = 18


def resolve_state_file() -> Optional[Path]:
    env_root = os.environ.get("BUDDY_ROOT")
    if env_root:
        return Path(env_root).expanduser() / "state.json"
    plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if plugin_data:
        candidate = Path(plugin_data).expanduser() / "state.json"
        if candidate.exists():
            return candidate

    plugins_root = Path.home() / ".claude" / "plugins" / "data"
    if plugins_root.is_dir():
        matches = sorted(
            (p for p in plugins_root.iterdir() if (p / "state.json").exists()),
            key=lambda p: ("buddy" not in p.name.lower(), p.stat().st_mtime * -1),
        )
        if matches:
            return matches[0] / "state.json"

    legacy = Path.home() / ".claude" / "buddy" / "state.json"
    if legacy.exists():
        return legacy
    return None


def _load_state(path: Path) -> Optional[dict]:
    try:
        raw = path.read_text()
    except OSError:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _bar(filled: int, total: int, width: int = BAR_WIDTH) -> str:
    if total <= 0:
        return "░" * width
    ratio = max(0.0, min(1.0, filled / total))
    lit = int(round(ratio * width))
    return "█" * lit + "░" * (width - lit)


def _render(state: Optional[dict], state_path: Optional[Path], width: int) -> str:
    lines: list[str] = []
    lines.append("─" * min(width, 60))
    lines.append("  buddy-pane")
    lines.append("─" * min(width, 60))
    if state is None:
        lines.append("")
        lines.append("  (no state file found)")
        lines.append("")
        lines.append("  Expected path: ~/.claude/plugins/data/<plugin>/state.json")
        lines.append("  or ~/.claude/buddy/state.json (legacy).")
        lines.append("")
        lines.append("  Run `/buddy:start` in Claude Code to create one.")
        return "\n".join(lines)
    buddy = state.get("buddy")
    if not buddy:
        lines.append("")
        lines.append("  No buddy yet. Run /buddy:start inside Claude Code.")
        lines.append("")
        return "\n".join(lines)

    name = buddy.get("name", "?")
    species_info = buddy.get("species_info") or {}
    species_name = species_info.get("display_name") or buddy.get("species", "?")
    level = buddy.get("level", 1)
    hp = buddy.get("current_hp", 0)
    max_hp = buddy.get("max_hp", max(1, hp))
    mp = buddy.get("current_mana", 0)
    max_mp = buddy.get("max_mana", max(1, mp))
    xp = buddy.get("xp", 0)
    xp_to_next = buddy.get("xp_to_next", max(1, xp))
    lines.append(f"  {name}  ({species_name} Lv{level})")
    lines.append(f"  HP {_bar(hp, max_hp)}  {hp}/{max_hp}")
    lines.append(f"  MP {_bar(mp, max_mp)}  {mp}/{max_mp}")
    lines.append(f"  XP {_bar(xp, xp_to_next)}  {xp}/{xp_to_next}")

    stats = buddy.get("stats") or {}
    if stats:
        # Stats display may use trailing underscore on reserved keys; strip.
        def _stat(k: str) -> str:
            return str(stats.get(k, stats.get(k.rstrip("_"), "?")))
        lines.append(
            "  ATK " + _stat("atk") + "  DEF " + _stat("def_") + "  SPD " + _stat("spd")
        )
        lines.append(
            "  LUCK " + _stat("luck") + "  INT " + _stat("int_") + "  RES " + _stat("res")
        )
    unspent = buddy.get("stat_points_unspent", 0)
    if unspent:
        lines.append(f"  {unspent} unspent stat points  (/buddy:allocate)")

    quest = buddy.get("quest")
    if quest:
        name = quest.get("name", quest.get("id", "?"))
        remaining = int(quest.get("remaining_s") or 0)
        if quest.get("done"):
            lines.append(f"  Quest: {name} — DONE  (/buddy:claim)")
        else:
            mm, ss = divmod(remaining, 60)
            lines.append(f"  Quest: {name} — {mm}m{ss:02d}s left")
    else:
        lines.append("  Quest: idle  (/buddy:quest)")

    recent = state.get("recent_events") or []
    if recent:
        lines.append("")
        lines.append("  Recent:")
        for ev in recent[-4:]:
            lines.append(f"    {ev}")
    lines.append("")
    lines.append(f"  (state: {state_path})  [ctrl-C to quit]")
    return "\n".join(lines)


def _reset_terminal() -> None:
    sys.stdout.write(SHOW_CURSOR)
    sys.stdout.flush()


def _install_signal_handlers() -> None:
    def _handler(signum, frame):  # type: ignore[no-untyped-def]
        _reset_terminal()
        sys.exit(0)
    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def main() -> int:
    _install_signal_handlers()
    state_path = resolve_state_file()
    try:
        sys.stdout.write(HIDE_CURSOR)
        while True:
            width = os.get_terminal_size(fallback=(60, 20)).columns
            state = _load_state(state_path) if state_path else None
            sys.stdout.write(CLEAR_SCREEN)
            sys.stdout.write(_render(state, state_path, width))
            sys.stdout.write("\n")
            sys.stdout.flush()
            time.sleep(REFRESH_SECONDS)
    finally:
        _reset_terminal()


if __name__ == "__main__":
    sys.exit(main())
