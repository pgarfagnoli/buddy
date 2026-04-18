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
        description="Quiet concentration. +2 success score on non-combat tasks. Costs 2 MP at quest claim.",
        mana_cost=2, trigger="passive_score", effect="flat_score_bonus",
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
        description="Hunts for the seam. +10% crit chance and +3 crit damage. 2 MP per encounter.",
        mana_cost=2, trigger="combat_passive", effect="crit_boost",
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
        description="An opening roar. +3 attack on the first strike of each encounter. 2 MP per encounter.",
        mana_cost=2, trigger="combat_passive", effect="opening_atk",
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
        description="A keen eye for trinkets. 25% chance to drop a bonus item when you clear an enemy. 1 MP per encounter.",
        mana_cost=1, trigger="on_enemy_kill", effect="bonus_item_pct",
        magnitude=25, passive=True,
    ),
    "executioner": Skill(
        id="executioner", name="Executioner",
        description="Hunts the wounded. Bonus damage when the enemy is under 25% HP. 2 MP per encounter.",
        mana_cost=2, trigger="combat_passive", effect="execute_bonus",
        magnitude=3, passive=True,
    ),
    "stoneblood": Skill(
        id="stoneblood", name="Stoneblood",
        description="Old, stubborn tissue. +2 effective defense in combat. 2 MP per encounter.",
        mana_cost=2, trigger="combat_passive", effect="extra_def",
        magnitude=2, passive=True,
    ),
    "counter": Skill(
        id="counter", name="Counter",
        description="Strikes back on reflex. 25% chance to hit back when struck. 2 MP per encounter.",
        mana_cost=2, trigger="combat_passive", effect="counter_chance",
        magnitude=25, passive=True,
    ),
    "mana_siphon": Skill(
        id="mana_siphon", name="Mana Siphon",
        description="Draws essence from fallen foes. +4 MP on enemy defeat. 1 MP per encounter (net positive).",
        mana_cost=1, trigger="on_enemy_kill", effect="mp_on_kill",
        magnitude=4, passive=True,
    ),
    "treasure_sense": Skill(
        id="treasure_sense", name="Treasure Sense",
        description="Knows where the good stuff is. Extra item on gathering success. 2 MP at quest claim.",
        mana_cost=2, trigger="on_success", effect="gathering_extra_item",
        magnitude=1, passive=True,
    ),
    "hearty": Skill(
        id="hearty", name="Hearty",
        description="Shakes off scratches. Regens 1 HP per second between encounters.",
        mana_cost=0, trigger="passive_regen", effect="out_of_combat_hp_regen",
        magnitude=1, passive=True,
    ),
    "bulwark": Skill(
        id="bulwark", name="Bulwark",
        description="Steadied posture. +1 effective defense in combat per 5 RES. 2 MP per encounter.",
        mana_cost=2, trigger="combat_passive", effect="extra_def_from_res",
        magnitude=5, passive=True,
    ),
    "dodge": Skill(
        id="dodge", name="Dodge",
        description="Reads the swing early. Enemies are 15% more likely to miss. 2 MP per encounter.",
        mana_cost=2, trigger="combat_passive", effect="dodge_chance",
        magnitude=15, passive=True,
    ),
    "double_strike": Skill(
        id="double_strike", name="Double Strike",
        description="A quick follow-up. 25% chance to land a second strike on the same beat. 2 MP per encounter.",
        mana_cost=2, trigger="combat_passive", effect="double_strike_chance",
        magnitude=25, passive=True,
    ),
    "rampage": Skill(
        id="rampage", name="Rampage",
        description="Builds momentum. +1 attack damage per landed strike, capped at +5, resets between fights. 2 MP per encounter.",
        mana_cost=2, trigger="combat_passive", effect="rampage_stack",
        magnitude=5, passive=True,
    ),
    "venom_fang": Skill(
        id="venom_fang", name="Venom Fang",
        description="Coats each strike with venom. Chance to poison the enemy scales with INT. 2 MP per encounter.",
        mana_cost=2, trigger="combat_passive", effect="apply_poison",
        magnitude=2, passive=True,
    ),
    "reflect_thorns": Skill(
        id="reflect_thorns", name="Reflect Thorns",
        description="Bristled hide stings attackers. Returns RES÷4 damage on every enemy strike. 2 MP per encounter.",
        mana_cost=2, trigger="combat_passive", effect="thorn_reflect",
        magnitude=4, passive=True,
    ),
    "mind_ward": Skill(
        id="mind_ward", name="Mind Ward",
        description="A practiced mental guard. Doubles RES-based status resistance. 2 MP per encounter.",
        mana_cost=2, trigger="combat_passive", effect="status_resist_double",
        magnitude=2, passive=True,
    ),
    "evade": Skill(
        id="evade", name="Evade",
        description="Slips around danger when the buddy spots it coming. INT-scaled chance to dodge an incoming encounter; 3 MP per dodge.",
        mana_cost=3, trigger="combat_spawn", effect="suppress_encounter",
        magnitude=1,
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
    ("bulwark", "res", 10),
    ("dodge", "spd", 18),
    ("double_strike", "atk", 15),
    ("rampage", "atk", 18),
    ("venom_fang", "int_", 12),
    ("reflect_thorns", "res", 12),
    ("mind_ward", "res", 10),
    ("evade", "int_", 12),
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


def is_engaged(buddy: "Buddy", skill_id: str) -> bool:
    """True if `skill_id` paid its mana cost at the start of the current
    encounter and is therefore "on" for this fight. Returns False outside
    of combat or when the engagement step skipped this skill (no MP).
    """
    return (
        buddy.combat is not None
        and skill_id in buddy.combat.engaged_skills
    )


_ENGAGED_TRIGGERS = frozenset({
    "combat_passive",  # vicious_strike, battle_cry, counter, etc — fight-wide effects
    "on_enemy_kill",   # lucky_find, mana_siphon — fight-wide effects, fire on each kill
})


def is_engagement_skill(skill: "Skill") -> bool:
    """True if a skill should be charged once per encounter via the
    engagement loop in `combat.try_spawn`. Filters by trigger type:
    `combat_passive` and `on_enemy_kill` are engagement skills (fight-wide).
    One-shot triggers (`combat_spawn`, `combat_reaction`) charge MP at
    their individual fire points instead. Non-combat triggers are excluded.
    """
    return skill.trigger in _ENGAGED_TRIGGERS


def prune_known_skills(buddy: "Buddy", inherent: tuple[str, ...]) -> list[str]:
    """Strip any known skill the buddy doesn't currently qualify for.

    Qualified sources:
      - The buddy's species inherent_skills (passed in by caller).
      - Meeting the current STAT_THRESHOLDS row for the skill.

    Mutates buddy.known_skills and buddy.active_skills in place. Returns
    the list of removed skill ids.
    """
    qualified: set[str] = set(inherent)
    for skill_id, stat_field, threshold in STAT_THRESHOLDS:
        if getattr(buddy.stats, stat_field, 0) >= threshold:
            qualified.add(skill_id)
    removed = [sid for sid in buddy.known_skills if sid not in qualified]
    buddy.known_skills = [sid for sid in buddy.known_skills if sid in qualified]
    buddy.active_skills = [sid for sid in buddy.active_skills if sid in qualified]
    return removed


def get_combat_modifier(buddy: "Buddy", hook: str) -> int:
    """Sum magnitudes of currently-engaged combat skills whose combat_hook matches.

    Reads from `buddy.combat.engaged_skills`, so a skill that didn't pay its
    mana at encounter spawn contributes nothing.
    """
    if buddy.combat is None:
        return 0
    total = 0
    for sid in buddy.combat.engaged_skills:
        s = SKILLS.get(sid)
        if s is None or s.combat_hook != hook:
            continue
        total += s.magnitude
    return total


def get_crit_bonus(buddy: "Buddy") -> int:
    """Flat extra damage added on a successful crit."""
    return 3 if is_engaged(buddy, "vicious_strike") else 0


def get_incoming_dmg_reduction(buddy: "Buddy") -> int:
    """Flat reduction subtracted from incoming enemy damage in combat."""
    return 1 if is_engaged(buddy, "iron_skin") else 0


def get_encounter_rate_mult(buddy: "Buddy") -> float:
    """Multiplier applied to `combat.BASE_SPAWN_PER_TICK`.

    Stacks two reductions:
      - `scout` (active): flat 0.5x — halves the spawn rate.
      - INT-based avoidance: -2% per INT point, capped at 60% reduction.
        A book-smart buddy notices threats early and routes around them.
    """
    mult = 1.0
    if has_active(buddy, "scout"):
        mult *= 0.5
    int_avoid = min(0.20, buddy.stats.int_ * 0.005)  # 0.5pp per INT, cap 20%
    mult *= 1.0 - int_avoid
    return mult


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
    """Flat def_ bonus folded into combat damage calc.

    Sources (only fire when engaged for this encounter):
      - stoneblood: flat +2.
      - bulwark: +1 per 5 RES (rounded down).
    """
    extra = 0
    if is_engaged(buddy, "stoneblood"):
        extra += 2
    if is_engaged(buddy, "bulwark"):
        extra += buddy.stats.res // 5
    return extra


def get_dodge_bonus(buddy: "Buddy") -> float:
    """Extra miss-chance for incoming enemy hits (0.0 - 1.0).

    Currently driven by the `dodge` active skill: +15% miss chance when engaged.
    """
    return 0.15 if is_engaged(buddy, "dodge") else 0.0


def get_execute_bonus(buddy: "Buddy", combat: Any) -> tuple[int, int]:
    """Return (flat_base_bonus, crit_dmg_pct_bonus) from executioner.

    Engaged only when the enemy's remaining HP is at or below 25% of its max.
    `combat` is the buddy's live `Combat` object (may be None).
    """
    if not is_engaged(buddy, "executioner") or combat is None:
        return 0, 0
    if combat.enemy_hp > combat.enemy_max_hp // 4:
        return 0, 0
    return 3, 50


def counter_chance(buddy: "Buddy") -> float:
    """Probability (0.0–1.0) that a counter fires on being hit."""
    return 0.25 if is_engaged(buddy, "counter") else 0.0


def try_mana_siphon(buddy: "Buddy") -> int:
    """On enemy kill, restore 4 MP if mana_siphon is engaged. Returns gained."""
    if not is_engaged(buddy, "mana_siphon"):
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
    The buddy must currently hold ≥ skill.mana_cost MP for the bonus to
    apply — we don't deduct MP here (this function is read multiple times
    per quest cycle), but we do require the budget exists so the skill
    feels like a real cost.
    """
    if getattr(qdef, "category", None) == "combat":
        return 0
    total = 0
    for sid in buddy.active_skills:
        s = SKILLS.get(sid)
        if s is None or s.effect != "flat_score_bonus":
            continue
        if buddy.current_mana < s.mana_cost:
            continue
        total += s.magnitude
    return total
