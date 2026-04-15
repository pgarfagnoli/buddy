"""Buddy skills: combat-aware passives, reactions, and non-combat passives.

Skills are learned from three sources (species-inherent, evolution grants,
stat-threshold unlocks) and live in two lists on `Buddy`:

- `known_skills`: every skill the buddy has ever learned. Unlimited.
- `active_skills`: the subset currently equipped. Cap: ACTIVE_SLOT_CAP.

Most skills read directly from `combat.py` via the helpers below
(`has_active`, `get_combat_modifier`, `try_consume_*`). Iron skin is the
one skill that still fires through the claim-time `_fire_skills()` path
in `quests.py` (its 50% on_failure damage reduction), AND participates in
combat as a passive flat damage reduction.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .state import Buddy


ACTIVE_SLOT_CAP = 4


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    description: str
    mana_cost: int
    # "on_failure" (claim-time, iron_skin only), or one of the new live-combat
    # markers: "passive_score", "passive_encounter_rate", "combat_spawn",
    # "combat_passive", "combat_reaction", "on_enemy_kill".
    trigger: str
    # "reduce_damage_pct" (claim), "flat_score_bonus", "encounter_rate_mult",
    # "preemptive_strike", "crit_boost", "opening_atk",
    # "emergency_heal_pct", "flee_encounter", "bonus_item_pct".
    effect: str
    magnitude: int
    # If non-empty, this skill contributes to `get_combat_modifier(buddy, hook)`.
    combat_hook: str = ""
    # Flags an always-on skill with no MP cost (for UI dimming hints).
    passive: bool = False


SKILLS: dict[str, Skill] = {
    "focus": Skill(
        id="focus", name="Focus",
        description="Quiet concentration. +2 success score on non-combat tasks.",
        mana_cost=0, trigger="passive_score", effect="flat_score_bonus",
        magnitude=2, passive=True,
    ),
    "scout": Skill(
        id="scout", name="Scout",
        description="Smells trouble before it lands. Halves combat encounter rate.",
        mana_cost=0, trigger="passive_encounter_rate",
        effect="encounter_rate_mult", magnitude=50, passive=True,
    ),
    "ambush": Skill(
        id="ambush", name="Ambush",
        description="Drops from cover with a free pre-emptive strike when a fight begins.",
        mana_cost=4, trigger="combat_spawn", effect="preemptive_strike",
        magnitude=1,
    ),
    "vicious_strike": Skill(
        id="vicious_strike", name="Vicious Strike",
        description="Hunts for the seam. +10% crit chance and +3 crit damage.",
        mana_cost=0, trigger="combat_passive", effect="crit_boost",
        magnitude=10, combat_hook="crit_chance", passive=True,
    ),
    "iron_skin": Skill(
        id="iron_skin", name="Iron Skin",
        description="Hardened hide shrugs off 1 damage per hit and halves damage on quest failure.",
        mana_cost=5, trigger="on_failure", effect="reduce_damage_pct",
        magnitude=50, passive=True,
    ),
    "battle_cry": Skill(
        id="battle_cry", name="Battle Cry",
        description="An opening roar. +3 attack on the first strike of each encounter.",
        mana_cost=0, trigger="combat_passive", effect="opening_atk",
        magnitude=3, passive=True,
    ),
    "second_wind": Skill(
        id="second_wind", name="Second Wind",
        description="Catches a breath from the brink. Spends 8 MP to heal 30% HP mid-fight.",
        mana_cost=8, trigger="combat_reaction", effect="emergency_heal_pct",
        magnitude=30,
    ),
    "swift_escape": Skill(
        id="swift_escape", name="Swift Escape",
        description="Outruns a losing fight. Spends 10 MP to flee without failing the quest.",
        mana_cost=10, trigger="combat_reaction", effect="flee_encounter",
        magnitude=1,
    ),
    "lucky_find": Skill(
        id="lucky_find", name="Lucky Find",
        description="A keen eye for trinkets. 25% chance to drop a bonus item when you clear an enemy.",
        mana_cost=0, trigger="on_enemy_kill", effect="bonus_item_pct",
        magnitude=25, passive=True,
    ),
    "executioner": Skill(
        id="executioner", name="Executioner",
        description="Hunts the wounded. Bonus damage when the enemy is under 25% HP.",
        mana_cost=0, trigger="combat_passive", effect="execute_bonus",
        magnitude=3, passive=True,
    ),
    "stoneblood": Skill(
        id="stoneblood", name="Stoneblood",
        description="Old, stubborn tissue. +2 effective defense in combat.",
        mana_cost=0, trigger="combat_passive", effect="extra_def",
        magnitude=2, passive=True,
    ),
    "counter": Skill(
        id="counter", name="Counter",
        description="Strikes back on reflex. 25% chance to hit back when struck.",
        mana_cost=0, trigger="combat_passive", effect="counter_chance",
        magnitude=25, passive=True,
    ),
    "mana_siphon": Skill(
        id="mana_siphon", name="Mana Siphon",
        description="Draws essence from fallen foes. +4 MP on enemy defeat.",
        mana_cost=0, trigger="on_enemy_kill", effect="mp_on_kill",
        magnitude=4, passive=True,
    ),
    "treasure_sense": Skill(
        id="treasure_sense", name="Treasure Sense",
        description="Knows where the good stuff is. Extra item on gathering success.",
        mana_cost=0, trigger="on_success", effect="gathering_extra_item",
        magnitude=1, passive=True,
    ),
    "hearty": Skill(
        id="hearty", name="Hearty",
        description="Shakes off scratches. Regens 1 HP per second between encounters.",
        mana_cost=0, trigger="passive_regen", effect="out_of_combat_hp_regen",
        magnitude=1, passive=True,
    ),
}


# (skill_id, stat_field_name, threshold)
STAT_THRESHOLDS: tuple[tuple[str, str, int], ...] = (
    ("focus", "int_", 10),
    ("iron_skin", "def_", 15),
    ("swift_escape", "spd", 20),
    ("second_wind", "hp", 30),
    ("lucky_find", "luck", 15),
    ("executioner", "atk", 18),
    ("stoneblood", "res", 15),
    ("counter", "spd", 15),
    ("mana_siphon", "int_", 18),
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


# ─── combat-side read surface ───────────────────────────────────────────────

def has_active(buddy: "Buddy", skill_id: str) -> bool:
    return skill_id in buddy.active_skills


def get_combat_modifier(buddy: "Buddy", hook: str) -> int:
    """Sum magnitudes of active skills whose combat_hook matches.

    Hooks currently in use:
      - "crit_chance" (percent points added to buddy crit chance)

    Skills whose numeric effect would collide with their claim-time
    magnitude (e.g. iron_skin=50) use dedicated helpers like
    `get_incoming_dmg_reduction` instead.
    """
    total = 0
    for sid in buddy.active_skills:
        s = SKILLS.get(sid)
        if s is None or s.combat_hook != hook:
            continue
        total += s.magnitude
    return total


def get_crit_bonus(buddy: "Buddy") -> int:
    """Flat extra damage added on a successful crit."""
    return 3 if has_active(buddy, "vicious_strike") else 0


def get_incoming_dmg_reduction(buddy: "Buddy") -> int:
    """Flat reduction subtracted from incoming enemy damage in combat."""
    return 1 if has_active(buddy, "iron_skin") else 0


def get_encounter_rate_mult(buddy: "Buddy") -> float:
    """Multiplier applied to `combat.BASE_SPAWN_PER_TICK`. Scout halves it."""
    return 0.5 if has_active(buddy, "scout") else 1.0


def try_consume_encounter_cost(buddy: "Buddy", skill_id: str) -> bool:
    """Charge a skill's MP cost once, typically on encounter spawn.

    Returns True iff the cost was charged. False means the skill is
    inactive, unknown, or the buddy didn't have enough mana.
    """
    s = SKILLS.get(skill_id)
    if s is None or skill_id not in buddy.active_skills:
        return False
    if buddy.current_mana < s.mana_cost:
        return False
    buddy.current_mana -= s.mana_cost
    return True


def try_consume_reaction_cost(buddy: "Buddy", skill_id: str) -> bool:
    """Same semantics as `try_consume_encounter_cost`; renamed for clarity
    at reaction-trigger call sites (second_wind / swift_escape)."""
    return try_consume_encounter_cost(buddy, skill_id)


def get_extra_def(buddy: "Buddy") -> int:
    """Flat def_ bonus folded into combat damage calc (stoneblood)."""
    return 2 if has_active(buddy, "stoneblood") else 0


def get_execute_bonus(buddy: "Buddy", combat: Any) -> tuple[int, int]:
    """Return (flat_base_bonus, crit_dmg_pct_bonus) from executioner.

    Active only when the enemy's remaining HP is at or below 25% of its max.
    `combat` is the buddy's live `Combat` object (may be None).
    """
    if not has_active(buddy, "executioner") or combat is None:
        return 0, 0
    if combat.enemy_hp > combat.enemy_max_hp // 4:
        return 0, 0
    return 3, 50


def counter_chance(buddy: "Buddy") -> float:
    """Probability (0.0–1.0) that a counter fires on being hit."""
    return 0.25 if has_active(buddy, "counter") else 0.0


def try_mana_siphon(buddy: "Buddy") -> int:
    """On enemy kill, restore 4 MP if mana_siphon is active. Returns gained."""
    if not has_active(buddy, "mana_siphon"):
        return 0
    before = buddy.current_mana
    buddy.current_mana = min(buddy.max_mana, buddy.current_mana + 4)
    return buddy.current_mana - before


def try_out_of_combat_regen(buddy: "Buddy") -> int:
    """Tick hearty regen: +1 HP per call when between encounters on any quest.

    Returns HP gained (0 if hearty isn't active, combat is live, or HP full).
    """
    if not has_active(buddy, "hearty"):
        return 0
    if buddy.combat is not None:
        return 0
    if buddy.current_hp >= buddy.stats.hp:
        return 0
    buddy.current_hp += 1
    return 1


def flat_score_bonus(buddy: "Buddy", qdef: Any) -> int:
    """Non-combat passive: +magnitude from `focus` on non-combat quests.

    Returns 0 on combat-category quests so focus stays flavor-true.
    """
    if getattr(qdef, "category", None) == "combat":
        return 0
    total = 0
    for sid in buddy.active_skills:
        s = SKILLS.get(sid)
        if s is None or s.effect != "flat_score_bonus":
            continue
        total += s.magnitude
    return total
