"""One-shot status line for Claude Code's statusLine setting.

Reads buddy state, prints a single compact line to stdout, and exits.
Designed to be fast — Claude Code runs this frequently.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from pane import resolve_state_file, _load_state  # noqa: E402
import leveling  # noqa: E402

RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"


def _compute_max_hp(stats: dict) -> int:
    return stats.get("hp", 10)


def _compute_max_mp(stats: dict) -> int:
    return 5 + stats.get("int", stats.get("int_", 5)) * 2


def _hp_color(hp: int, max_hp: int) -> str:
    if max_hp <= 0:
        return RED
    ratio = hp / max_hp
    if ratio > 0.5:
        return GREEN
    if ratio > 0.25:
        return YELLOW
    return RED


def main() -> int:
    state_path = resolve_state_file()
    if not state_path:
        print("(no buddy yet)")
        return 0
    state = _load_state(state_path)
    if not state or not state.get("buddy"):
        print("(no buddy yet)")
        return 0

    b = state["buddy"]
    name = b.get("name", "?")
    info = b.get("species_info") or {}
    species = info.get("display_name") or b.get("species", "?").replace("_", " ").title()
    level = b.get("level", 1)
    stats = b.get("stats") or {}
    hp = b.get("current_hp", 0)
    max_hp = _compute_max_hp(stats)
    mp = b.get("current_mana", 0)
    max_mp = _compute_max_mp(stats)
    xp = b.get("xp", 0)
    xp_next = leveling.xp_to_next(level)

    hp_c = _hp_color(hp, max_hp)

    quest = b.get("quest")
    if quest:
        q_name = quest.get("name", quest.get("id", "?"))
        if quest.get("done"):
            quest_str = f"{GREEN}{q_name} DONE!{RESET}"
        else:
            remaining = int(quest.get("remaining_s") or 0)
            mm, ss = divmod(remaining, 60)
            quest_str = f"{CYAN}{q_name} {mm}m{ss:02d}s{RESET}"
    else:
        quest_str = f"{CYAN}idle{RESET}"

    print(
        f"{BOLD}{name}{RESET} ({species} Lv{level}) "
        f"{hp_c}HP {hp}/{max_hp}{RESET} {BLUE}MP {mp}/{max_mp}{RESET} {YELLOW}XP {xp}/{xp_next}{RESET} "
        f"| {quest_str}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
