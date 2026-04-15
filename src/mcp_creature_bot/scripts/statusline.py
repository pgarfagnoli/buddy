"""Compact buddy summary for Claude Code statusLine.

Reads state and emits a single line. Plain text, handles no-buddy case.
"""
from __future__ import annotations

import sys

from .. import leveling, species
from ..state import load_state


BAR_WIDTH = 6


def _bar(current: int, maximum: int, width: int = BAR_WIDTH) -> str:
    if maximum <= 0:
        filled = 0
    else:
        filled = max(0, min(width, int(round(width * current / maximum))))
    return "█" * filled + "░" * (width - filled)


def main() -> int:
    # stdin payload from Claude Code (ignored — we just need state)
    try:
        sys.stdin.read()
    except Exception:
        pass
    try:
        state = load_state()
    except Exception:
        return 0
    if state.buddy is None:
        sys.stdout.write("[ no buddy — run /buddy to pick a starter ]")
        return 0
    b = state.buddy
    parts = [
        f"🐲 {b.name}",
        f"Lv{b.level}",
        f"HP {_bar(b.current_hp, b.max_hp)}",
        f"MP {_bar(b.current_mana, b.max_mana)}",
        f"XP {_bar(b.xp, leveling.xp_to_next(b.level, species.get_tier(b.species)))}",
    ]
    if b.stat_points_unspent:
        parts.append(f"⚡{b.stat_points_unspent}")
    if b.quest:
        rem = b.quest.remaining()
        tag = "✓done" if rem == 0 else f"{rem // 60}m{rem % 60:02d}"
        parts.append(f"quest {tag}")
    sys.stdout.write("  ".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
