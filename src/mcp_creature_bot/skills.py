"""Buddy skills: passive abilities that fire at quest-claim time.

Skills are learned from three sources (species-inherent, evolution grants,
stat-threshold unlocks) and live in two lists on `Buddy`:

- `known_skills`: every skill the buddy has ever learned. Unlimited.
- `active_skills`: the subset currently equipped. Cap: ACTIVE_SLOT_CAP.

At claim time, every active skill whose trigger matches the outcome fires,
provided the buddy has enough mana to cover its cost. Firing drains mana.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import Buddy


ACTIVE_SLOT_CAP = 4


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    description: str
    mana_cost: int
    trigger: str    # "on_claim" | "on_success" | "on_failure"
    effect: str     # "boost_success" | "bonus_xp_pct" | "heal_pct" |
                    # "reduce_damage_pct" | "extra_loot_roll"
    magnitude: int


SKILLS: dict[str, Skill] = {
    "focus": Skill(
        id="focus", name="Focus",
        description="Sharpens intent before the strike. +15% success chance.",
        mana_cost=5, trigger="on_claim", effect="boost_success", magnitude=15,
    ),
    "scout": Skill(
        id="scout", name="Scout",
        description="A quick look ahead. +8% success chance.",
        mana_cost=3, trigger="on_claim", effect="boost_success", magnitude=8,
    ),
    "ambush": Skill(
        id="ambush", name="Ambush",
        description="Strike from hiding. +12% success chance.",
        mana_cost=4, trigger="on_claim", effect="boost_success", magnitude=12,
    ),
    "vicious_strike": Skill(
        id="vicious_strike", name="Vicious Strike",
        description="A precise killing blow. +18% success chance.",
        mana_cost=6, trigger="on_claim", effect="boost_success", magnitude=18,
    ),
    "iron_skin": Skill(
        id="iron_skin", name="Iron Skin",
        description="Hardened hide. Halves HP damage on failure.",
        mana_cost=5, trigger="on_failure", effect="reduce_damage_pct", magnitude=50,
    ),
    "swift_escape": Skill(
        id="swift_escape", name="Swift Escape",
        description="Outrun the consequences. Negates HP damage on failure.",
        mana_cost=10, trigger="on_failure", effect="reduce_damage_pct", magnitude=100,
    ),
    "second_wind": Skill(
        id="second_wind", name="Second Wind",
        description="Catch a breath after a loss. Heals 30% of max HP on failure.",
        mana_cost=8, trigger="on_failure", effect="heal_pct", magnitude=30,
    ),
    "lucky_find": Skill(
        id="lucky_find", name="Lucky Find",
        description="A keen eye for loot. Extra item on success.",
        mana_cost=5, trigger="on_success", effect="extra_loot_roll", magnitude=1,
    ),
    "battle_cry": Skill(
        id="battle_cry", name="Battle Cry",
        description="A triumphant roar. +25% XP on success.",
        mana_cost=8, trigger="on_success", effect="bonus_xp_pct", magnitude=25,
    ),
}


# (skill_id, stat_field_name, threshold)
STAT_THRESHOLDS: tuple[tuple[str, str, int], ...] = (
    ("focus", "int_", 10),
    ("iron_skin", "def_", 15),
    ("swift_escape", "spd", 20),
    ("second_wind", "hp", 30),
    ("lucky_find", "luck", 15),
)


def get(skill_id: str) -> Skill:
    if skill_id not in SKILLS:
        raise KeyError(f"unknown skill: {skill_id!r}")
    return SKILLS[skill_id]


def all_skills() -> list[Skill]:
    return list(SKILLS.values())


def _learn(buddy: "Buddy", skill_id: str) -> bool:
    """Append to known_skills if new; auto-fill an active slot if room.

    Returns True iff this was a new skill for the buddy.
    """
    if skill_id not in SKILLS:
        return False
    if skill_id in buddy.known_skills:
        return False
    buddy.known_skills.append(skill_id)
    if len(buddy.active_skills) < ACTIVE_SLOT_CAP:
        buddy.active_skills.append(skill_id)
    return True


def check_and_grant_skills(buddy: "Buddy") -> list[str]:
    """Grant any skills the buddy now qualifies for and hasn't learned yet.

    Checks (in order):
      1. Species-inherent skills from the current species.
      2. Stat-threshold unlocks per STAT_THRESHOLDS.

    Returns the list of newly learned skill ids (for event logging).
    Idempotent: calling twice in a row with no state change grants nothing.
    """
    from . import species  # local import to avoid cycles
    newly: list[str] = []

    try:
        sp = species.get(buddy.species)
    except KeyError:
        sp = None
    if sp is not None:
        for sid in sp.inherent_skills:
            if _learn(buddy, sid):
                newly.append(sid)

    for sid, stat_name, threshold in STAT_THRESHOLDS:
        if getattr(buddy.stats, stat_name, 0) >= threshold:
            if _learn(buddy, sid):
                newly.append(sid)

    return newly
