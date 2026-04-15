"""Idle combat encounters that spawn during combat-category quests.

The pane's 1 Hz loop drives this module: on each tick it calls
`try_spawn` (if no encounter is active) or `tick_encounter` (if one is).
All state lives on `Buddy.combat` (an Optional[Combat] in state.py).

No I/O here — callers invoke these helpers from inside `mutate_state` so
the surrounding flock keeps things consistent.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from . import skills
from .quests import QuestDef
from .state import Buddy, Combat


# ─── tunables ───────────────────────────────────────────────────────────────

ROUND_INTERVAL_S = 2           # one combat round every N seconds
ENCOUNTER_COOLDOWN_S = 30      # minimum gap between successive encounters
BASE_SPAWN_PER_TICK = 0.04     # roll per tick once the cooldown has elapsed
LOG_CAP = 4                    # last N combat lines rendered in the pane


# ─── enemy registry ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EnemyDef:
    id: str
    name: str
    zone: str
    glyph: str
    hp: int
    atk: int
    def_: int
    spd: int
    xp_reward: int
    flavor_hit: tuple[str, ...]
    flavor_miss: tuple[str, ...]


ENEMIES: dict[str, EnemyDef] = {
    # ─── forest ─────────────────────────────────────────────────────────────
    "forest_spiderling": EnemyDef(
        id="forest_spiderling", name="spiderling", zone="forest", glyph="ᯓ",
        hp=12, atk=4, def_=2, spd=6, xp_reward=5,
        flavor_hit=("lunges with dripping fangs", "jabs a barbed leg"),
        flavor_miss=("scrabbles at empty air", "skitters sideways"),
    ),
    "forest_wasp": EnemyDef(
        id="forest_wasp", name="forest wasp", zone="forest", glyph="~",
        hp=9, atk=5, def_=1, spd=9, xp_reward=5,
        flavor_hit=("drives its stinger home", "dive-bombs"),
        flavor_miss=("circles angrily", "buzzes past the ear"),
    ),
    "forest_thornling": EnemyDef(
        id="forest_thornling", name="thornling", zone="forest", glyph="*",
        hp=16, atk=3, def_=4, spd=3, xp_reward=6,
        flavor_hit=("flails a thorn-whip", "jabs with needled vines"),
        flavor_miss=("sways off balance", "tangles in itself"),
    ),

    # ─── cave ───────────────────────────────────────────────────────────────
    "cave_bat": EnemyDef(
        id="cave_bat", name="cave bat", zone="cave", glyph="^",
        hp=14, atk=5, def_=2, spd=10, xp_reward=7,
        flavor_hit=("swoops and scratches", "rakes with tiny claws"),
        flavor_miss=("veers into shadow", "screeches overhead"),
    ),
    "cave_slime": EnemyDef(
        id="cave_slime", name="cave slime", zone="cave", glyph="●",
        hp=22, atk=4, def_=5, spd=2, xp_reward=7,
        flavor_hit=("slaps a cold pseudopod", "engulfs a paw"),
        flavor_miss=("quivers uselessly", "oozes sideways"),
    ),
    "cave_crawler": EnemyDef(
        id="cave_crawler", name="rock crawler", zone="cave", glyph="#",
        hp=18, atk=6, def_=4, spd=4, xp_reward=8,
        flavor_hit=("snips with stony pincers", "clamps down hard"),
        flavor_miss=("grinds across wet stone", "misjudges the leap"),
    ),

    # ─── ruins ──────────────────────────────────────────────────────────────
    "ruins_wight": EnemyDef(
        id="ruins_wight", name="ruin wight", zone="ruins", glyph="†",
        hp=26, atk=8, def_=5, spd=5, xp_reward=12,
        flavor_hit=("lashes with a wraith-hand", "drains a breath of warmth"),
        flavor_miss=("slips through itself", "moans and reforms"),
    ),
    "ruins_ward": EnemyDef(
        id="ruins_ward", name="stone ward", zone="ruins", glyph="◆",
        hp=34, atk=7, def_=8, spd=3, xp_reward=13,
        flavor_hit=("swings a carved fist", "grinds out a ward-strike"),
        flavor_miss=("locks up mid-swing", "misreads the pattern"),
    ),
    "ruins_echo": EnemyDef(
        id="ruins_echo", name="echo shade", zone="ruins", glyph="§",
        hp=22, atk=9, def_=4, spd=8, xp_reward=13,
        flavor_hit=("blasts a dissonant chord", "resonates the air"),
        flavor_miss=("flickers out of tune", "chases its own echo"),
    ),

    # ─── peaks ──────────────────────────────────────────────────────────────
    "peaks_frostling": EnemyDef(
        id="peaks_frostling", name="frostling", zone="peaks", glyph="❄",
        hp=28, atk=9, def_=6, spd=7, xp_reward=18,
        flavor_hit=("swings an icicle-blade", "exhales a freezing gust"),
        flavor_miss=("slides across the ice", "shatters a wild strike"),
    ),
    "peaks_raptor": EnemyDef(
        id="peaks_raptor", name="ridge raptor", zone="peaks", glyph="v",
        hp=24, atk=11, def_=4, spd=12, xp_reward=19,
        flavor_hit=("stoops from above", "rakes with long talons"),
        flavor_miss=("banks wide on a gust", "cries overhead"),
    ),
    "peaks_wyvern": EnemyDef(
        id="peaks_wyvern", name="cliff wyvern", zone="peaks", glyph="W",
        hp=42, atk=12, def_=8, spd=6, xp_reward=22,
        flavor_hit=("bites down with a crack", "whips its tail"),
        flavor_miss=("overshoots the lunge", "beats its wings in frustration"),
    ),
}


ZONE_ENEMIES: dict[str, tuple[str, ...]] = {
    "forest": ("forest_spiderling", "forest_wasp", "forest_thornling"),
    "cave": ("cave_bat", "cave_slime", "cave_crawler"),
    "ruins": ("ruins_wight", "ruins_ward", "ruins_echo"),
    "peaks": ("peaks_frostling", "peaks_raptor", "peaks_wyvern"),
}


class TickResult(Enum):
    WAITING = "waiting"         # round interval not yet elapsed
    ONGOING = "ongoing"         # round resolved, both still standing
    BUDDY_WIN = "buddy_win"     # enemy down, encounter cleared
    BUDDY_DOWN = "buddy_down"   # buddy retreats, caller must fail quest


# ─── helpers ────────────────────────────────────────────────────────────────

def _quest_zone(qdef: QuestDef) -> Optional[str]:
    """Derive zone id from the quest id prefix. Unknown → None."""
    for zone in ZONE_ENEMIES:
        if qdef.id.startswith(zone + "_"):
            return zone
    return None


def get_enemy(enemy_id: str) -> EnemyDef:
    if enemy_id not in ENEMIES:
        raise KeyError(f"unknown enemy: {enemy_id!r}")
    return ENEMIES[enemy_id]


def _push_log(combat: Combat, line: str) -> None:
    combat.log.append(line)
    if len(combat.log) > LOG_CAP:
        combat.log = combat.log[-LOG_CAP:]


# ─── spawn / tick ───────────────────────────────────────────────────────────

def pick_enemy_for_quest(qdef: QuestDef, rng: random.Random) -> Optional[EnemyDef]:
    zone = _quest_zone(qdef)
    if zone is None:
        return None
    pool = ZONE_ENEMIES.get(zone, ())
    if not pool:
        return None
    return ENEMIES[rng.choice(pool)]


def try_spawn(buddy: Buddy, qdef: QuestDef, now: int, rng: random.Random) -> bool:
    """Spawn an encounter if the quest is risky and the dice agree."""
    if buddy.combat is not None:
        return False
    if qdef.category != "combat":
        return False
    if qdef.hp_penalty_pct_on_failure <= 0:
        # Meadow combat-tagged chase quests (butterfly/pollen/rabbit): safe, no enemies.
        return False
    if buddy.last_combat_spawn_at and (now - buddy.last_combat_spawn_at) < ENCOUNTER_COOLDOWN_S:
        return False
    if rng.random() > BASE_SPAWN_PER_TICK * skills.get_encounter_rate_mult(buddy):
        return False
    enemy = pick_enemy_for_quest(qdef, rng)
    if enemy is None:
        return False
    buddy.combat = Combat(
        enemy_id=enemy.id,
        enemy_hp=enemy.hp,
        enemy_max_hp=enemy.hp,
        started_at=now,
        last_round_at=now,
        log=[f"a {enemy.name} appears!"],
    )
    buddy.last_combat_spawn_at = now

    # Ambush: free pre-emptive strike on encounter spawn, charged once.
    if skills.try_consume_encounter_cost(buddy, "ambush"):
        dmg, _crit = _buddy_attack(buddy, enemy, rng)
        buddy.combat.enemy_hp = max(0, buddy.combat.enemy_hp - dmg)
        _push_log(buddy.combat, f"{buddy.name} ambushes for {dmg}!")
        if buddy.combat.enemy_hp <= 0:
            buddy.xp += enemy.xp_reward
            _push_log(buddy.combat, f"{enemy.name} is defeated (+{enemy.xp_reward} xp)")
            _roll_lucky_find(buddy, qdef, rng)
            _roll_mana_siphon(buddy)
            buddy.combat = None
    return True


def _buddy_attack(buddy: Buddy, enemy: EnemyDef, rng: random.Random) -> tuple[int, bool]:
    """Return (damage_dealt, crit?).

    Skill hooks:
      - vicious_strike: +10% crit chance (lifts the ceiling) and +3 crit dmg
      - battle_cry: +3 base damage on the first strike of an encounter
      - executioner: +3 base damage and +50% crit bonus when enemy HP ≤ 25%
    """
    extra_crit_pct = skills.get_combat_modifier(buddy, "crit_chance") / 100.0
    crit_cap = 0.35 + extra_crit_pct
    crit_chance = min(crit_cap, 0.05 + buddy.stats.luck * 0.01 + extra_crit_pct)
    crit = rng.random() < crit_chance
    base = max(1, buddy.stats.atk - enemy.def_ + rng.randint(-1, 1))
    if (
        buddy.combat is not None
        and buddy.combat.enemy_hp == buddy.combat.enemy_max_hp
        and skills.has_active(buddy, "battle_cry")
    ):
        base += 3
    exec_flat, exec_crit_pct = skills.get_execute_bonus(buddy, buddy.combat)
    base += exec_flat
    if crit:
        crit_bonus = buddy.stats.atk // 2 + 1 + skills.get_crit_bonus(buddy)
        if exec_crit_pct:
            crit_bonus = crit_bonus * (100 + exec_crit_pct) // 100
        base += crit_bonus
    return base, crit


def _enemy_attack(buddy: Buddy, enemy: EnemyDef, rng: random.Random) -> tuple[int, bool]:
    """Return (damage_dealt, hit?). Enemy whiffs occasionally based on buddy spd."""
    hit = rng.random() >= min(0.35, 0.05 + max(0, buddy.stats.spd - enemy.spd) * 0.02)
    if not hit:
        return 0, False
    dmg = max(
        1,
        enemy.atk - buddy.stats.def_ - skills.get_extra_def(buddy)
          + rng.randint(-1, 1)
          - skills.get_incoming_dmg_reduction(buddy),
    )
    return dmg, True


def _roll_mana_siphon(buddy: Buddy) -> None:
    """If mana_siphon is active, restore MP and log it."""
    gained = skills.try_mana_siphon(buddy)
    if gained and buddy.combat is not None:
        _push_log(buddy.combat, f"{buddy.name} siphons {gained} MP")


def _roll_lucky_find(buddy: Buddy, qdef: QuestDef, rng: random.Random) -> None:
    """If lucky_find is active, maybe drop a bonus quest item on enemy kill."""
    if not skills.has_active(buddy, "lucky_find"):
        return
    if not qdef.items_on_success:
        return
    skill = skills.SKILLS.get("lucky_find")
    chance = (skill.magnitude if skill is not None else 0) / 100.0
    if rng.random() >= chance:
        return
    item = rng.choice(list(qdef.items_on_success))
    buddy.inventory.append(item)
    if buddy.combat is not None:
        _push_log(buddy.combat, f"{buddy.name} found a {item}!")


def tick_encounter(
    buddy: Buddy, qdef: QuestDef, now: int, rng: random.Random,
) -> TickResult:
    """Advance at most one round. HP floors at 1 and triggers BUDDY_DOWN.

    `qdef` is the active quest — threaded through so `lucky_find` can read
    `items_on_success` when the buddy clears an enemy.
    """
    combat = buddy.combat
    if combat is None:
        return TickResult.WAITING
    if (now - combat.last_round_at) < ROUND_INTERVAL_S:
        return TickResult.WAITING
    try:
        enemy = get_enemy(combat.enemy_id)
    except KeyError:
        buddy.combat = None
        return TickResult.BUDDY_WIN  # enemy definition missing — treat as clear

    combat.last_round_at = now
    buddy_first = buddy.stats.spd >= enemy.spd

    def strike_buddy() -> Optional[TickResult]:
        dmg, crit = _buddy_attack(buddy, enemy, rng)
        combat.enemy_hp = max(0, combat.enemy_hp - dmg)
        _push_log(combat, f"{buddy.name} {'crits' if crit else 'hits'} for {dmg}")
        if combat.enemy_hp <= 0:
            buddy.xp += enemy.xp_reward
            _push_log(combat, f"{enemy.name} is defeated (+{enemy.xp_reward} xp)")
            _roll_lucky_find(buddy, qdef, rng)
            _roll_mana_siphon(buddy)
            buddy.combat = None
            return TickResult.BUDDY_WIN
        return None

    def strike_enemy() -> Optional[TickResult]:
        dmg, hit = _enemy_attack(buddy, enemy, rng)
        if not hit:
            _push_log(combat, f"{enemy.name} {rng.choice(enemy.flavor_miss)}")
            return None
        new_hp = max(1, buddy.current_hp - dmg)
        taken = buddy.current_hp - new_hp
        buddy.current_hp = new_hp
        _push_log(combat, f"{enemy.name} {rng.choice(enemy.flavor_hit)} (-{taken})")
        # Counter: strike back on reflex. Fires even on what would be a fatal blow.
        if rng.random() < skills.counter_chance(buddy):
            ctr = max(1, buddy.stats.atk // 2)
            combat.enemy_hp = max(0, combat.enemy_hp - ctr)
            _push_log(combat, f"{buddy.name} counters for {ctr}!")
            if combat.enemy_hp <= 0:
                buddy.xp += enemy.xp_reward
                _push_log(combat, f"{enemy.name} is defeated (+{enemy.xp_reward} xp)")
                _roll_lucky_find(buddy, qdef, rng)
                _roll_mana_siphon(buddy)
                buddy.combat = None
                return TickResult.BUDDY_WIN
        if buddy.current_hp <= 1:
            # Reaction chain: second_wind keeps you fighting, swift_escape
            # flees cleanly, otherwise BUDDY_DOWN fails the quest.
            if skills.try_consume_reaction_cost(buddy, "second_wind"):
                healed = max(1, buddy.stats.hp * 30 // 100)
                buddy.current_hp = healed
                _push_log(combat, f"{buddy.name} catches a second wind!")
                return None
            if skills.try_consume_reaction_cost(buddy, "swift_escape"):
                buddy.current_hp = max(buddy.current_hp, buddy.stats.hp // 4)
                _push_log(combat, f"{buddy.name} slips away!")
                buddy.combat = None
                return TickResult.ONGOING
            _push_log(combat, f"{buddy.name} staggers — retreating!")
            buddy.combat = None
            return TickResult.BUDDY_DOWN
        return None

    order = (strike_buddy, strike_enemy) if buddy_first else (strike_enemy, strike_buddy)
    for fn in order:
        outcome = fn()
        if outcome is not None:
            return outcome
        if buddy.combat is None:
            # A reaction (e.g. swift_escape) cleared the encounter mid-round.
            return TickResult.ONGOING
    return TickResult.ONGOING
