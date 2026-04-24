"""Idle combat encounters that spawn during combat-category quests.

The pane's 1 Hz loop drives this module: on each tick it calls
`try_spawn` (if no encounter is active) or `tick_encounter` (if one is).
All state lives on `Buddy.combat` (an Optional[Combat] in state.py).

No I/O here — callers invoke these helpers from inside `mutate_state` so
the surrounding flock keeps things consistent.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import paths
import skills
from quests import QuestDef
from species import _parse_sprite_file
from state import Buddy, Combat


# ─── tunables ───────────────────────────────────────────────────────────────

BASE_STRIKE_INTERVAL_S = 3     # cadence at the baseline speed (whole seconds)
BASELINE_SPD = 15              # spd 15 ⇒ exactly base interval (spd 22 hare → 2s, spd 6 spider → 6s)
MIN_STRIKE_INTERVAL_S = 2      # floor so very fast attackers don't spam every tick
MAX_STRIKE_INTERVAL_S = 6      # ceiling so very slow attackers still poke
ENCOUNTER_COOLDOWN_S = 30      # minimum gap between successive encounters
BASE_SPAWN_PER_TICK = 0.04     # roll per tick once the cooldown has elapsed
LOG_CAP = 4                    # last N combat lines rendered in the pane

# ─── skill formula tunables (centralized for easy rebalancing) ─────────────
EVADE_BASE_PCT = 0.30          # base avoid chance for the evade skill
EVADE_INT_SCALE = 0.02         # additional avoid % per point of INT
EVADE_CAP = 0.75               # hard cap on evade avoid chance
EVADE_MANA_COST = 3            # MP consumed per successful evade
VENOM_BASE_PCT = 30            # base poison apply chance for venom_fang
VENOM_INT_SCALE_DIV = 2        # int_ // this → added to base apply %
VENOM_CAP_PCT = 75             # hard cap on venom apply chance
VENOM_DAMAGE = 2               # poison damage per tick
VENOM_DURATION = 3             # poison ticks (strikes) before expiring
THORN_RES_DIVISOR = 4          # reflect_thorns: res // this = reflect damage
LURE_INT_DIVISOR = 2           # lure weighting: edge = lure - int_ // this
DODGE_MISS_BASE = 0.05         # baseline miss chance for enemy attacks
DODGE_SPD_SCALE = 0.01         # additional miss % per SPD advantage point
DODGE_CAP = 0.25               # hard cap on total miss chance
MAX_COMBAT_DURATION_S = 120    # force escape after 2 min to prevent infinite fights


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
    lure: int = 0  # >0 = enemy has the lure trait; weights pool pick + grants free ambush on spawn


ENEMIES: dict[str, EnemyDef] = {
    # HP rebalanced ~1.7× from earlier values so fights last 3–5 rounds.
    # ─── forest ─────────────────────────────────────────────────────────────
    "forest_spiderling": EnemyDef(
        id="forest_spiderling", name="spiderling", zone="forest", glyph="ᯓ",
        hp=58, atk=4, def_=2, spd=6, xp_reward=10,
        flavor_hit=("lunges with dripping fangs", "jabs a barbed leg"),
        flavor_miss=("scrabbles at empty air", "skitters sideways"),
    ),
    "forest_wasp": EnemyDef(
        id="forest_wasp", name="forest wasp", zone="forest", glyph="~",
        hp=44, atk=5, def_=1, spd=9, xp_reward=10,
        flavor_hit=("drives its stinger home", "dive-bombs"),
        flavor_miss=("circles angrily", "buzzes past the ear"),
    ),
    "forest_centipede": EnemyDef(
        id="forest_centipede", name="giant centipede", zone="forest", glyph="*",
        hp=72, atk=3, def_=4, spd=3, xp_reward=13,
        flavor_hit=("clamps with venomous forcipules", "wraps a paw in segmented coils"),
        flavor_miss=("thrashes against a root", "rears up but misjudges"),
    ),

    # ─── cave ───────────────────────────────────────────────────────────────
    "cave_bat": EnemyDef(
        id="cave_bat", name="cave bat", zone="cave", glyph="^",
        hp=24, atk=5, def_=2, spd=10, xp_reward=7,
        flavor_hit=("swoops and scratches", "rakes with tiny claws"),
        flavor_miss=("veers into shadow", "screeches overhead"),
    ),
    "cave_olm": EnemyDef(
        id="cave_olm", name="cave olm", zone="cave", glyph="●",
        hp=38, atk=4, def_=5, spd=2, xp_reward=7,
        flavor_hit=("clamps a slick jaw", "thrashes with a pale tail"),
        flavor_miss=("slips on wet stone", "lunges and falls short"),
    ),
    "cave_isopod": EnemyDef(
        id="cave_isopod", name="giant isopod", zone="cave", glyph="#",
        hp=32, atk=6, def_=4, spd=4, xp_reward=8,
        flavor_hit=("crunches with armored mandibles", "rolls and slams"),
        flavor_miss=("scrapes uselessly across stone", "misjudges the leap"),
    ),
    "cave_angler": EnemyDef(
        id="cave_angler", name="cave angler", zone="cave", glyph="◓",
        hp=44, atk=8, def_=3, spd=4, xp_reward=14, lure=10,
        flavor_hit=("snaps with needle teeth", "lights its lure and lunges"),
        flavor_miss=("the lure flickers harmlessly", "missteps in the dark"),
    ),

    # ─── ruins ──────────────────────────────────────────────────────────────
    "ruins_packrat": EnemyDef(
        id="ruins_packrat", name="pack rat", zone="ruins", glyph="r",
        hp=44, atk=8, def_=5, spd=5, xp_reward=12,
        flavor_hit=("bites with chisel teeth", "lashes with its tail"),
        flavor_miss=("ducks behind a stone", "scurries off-line"),
    ),
    "ruins_scorpion": EnemyDef(
        id="ruins_scorpion", name="desert scorpion", zone="ruins", glyph="◆",
        hp=58, atk=7, def_=8, spd=3, xp_reward=13,
        flavor_hit=("strikes with a venom-tipped tail", "clamps with armored pincers"),
        flavor_miss=("rattles its sting", "snaps at empty air"),
    ),
    "ruins_swift": EnemyDef(
        id="ruins_swift", name="cliff swift", zone="ruins", glyph="§",
        hp=38, atk=9, def_=4, spd=8, xp_reward=13,
        flavor_hit=("dives at full tilt", "rakes with sharp talons"),
        flavor_miss=("banks wide and screeches", "overshoots the dive"),
    ),

    # ─── peaks ──────────────────────────────────────────────────────────────
    "peaks_ermine": EnemyDef(
        id="peaks_ermine", name="ermine", zone="peaks", glyph="❄",
        hp=48, atk=9, def_=6, spd=7, xp_reward=18,
        flavor_hit=("darts in for a throat bite", "claws in a flurry"),
        flavor_miss=("vanishes into the snow", "feints and circles"),
    ),
    "peaks_raptor": EnemyDef(
        id="peaks_raptor", name="ridge hawk", zone="peaks", glyph="v",
        hp=42, atk=11, def_=4, spd=12, xp_reward=19,
        flavor_hit=("stoops from above", "rakes with long talons"),
        flavor_miss=("banks wide on a gust", "cries overhead"),
    ),
    "peaks_andean_condor": EnemyDef(
        id="peaks_andean_condor", name="Andean condor", zone="peaks", glyph="W",
        hp=72, atk=12, def_=8, spd=6, xp_reward=22,
        flavor_hit=("drops talons-first from a thermal", "lashes a 10-foot wing"),
        flavor_miss=("overshoots the lunge", "circles back into the wind"),
    ),
    # ─── Phase 3 additions: 7 new real enemies for zone variety ─────────────
    "forest_viper": EnemyDef(
        id="forest_viper", name="forest viper", zone="forest", glyph="s",
        hp=34, atk=6, def_=2, spd=7, xp_reward=9,
        flavor_hit=("strikes from a low coil", "sinks fangs into a hindleg"),
        flavor_miss=("misjudges the lunge", "slithers off-line"),
    ),
    "cave_centipede": EnemyDef(
        id="cave_centipede", name="cave centipede", zone="cave", glyph="*",
        hp=36, atk=5, def_=3, spd=6, xp_reward=8,
        flavor_hit=("clamps with venomous forcipules", "wraps a paw in coils"),
        flavor_miss=("rears up but misjudges", "thrashes against a stone"),
    ),
    "cave_crayfish": EnemyDef(
        id="cave_crayfish", name="cave crayfish", zone="cave", glyph="C",
        hp=28, atk=4, def_=6, spd=3, xp_reward=7,
        flavor_hit=("snips with a pale claw", "clamps an armored pincer"),
        flavor_miss=("snaps at empty water", "scuttles backward"),
    ),
    "ruins_rattlesnake": EnemyDef(
        id="ruins_rattlesnake", name="rattlesnake", zone="ruins", glyph="z",
        hp=42, atk=9, def_=3, spd=6, xp_reward=12,
        flavor_hit=("strikes with a venom-loaded bite", "rattles, then lunges"),
        flavor_miss=("hisses and coils tighter", "withdraws into a crevice"),
    ),
    "ruins_jackal": EnemyDef(
        id="ruins_jackal", name="golden jackal", zone="ruins", glyph="j",
        hp=46, atk=10, def_=5, spd=12, xp_reward=14,
        flavor_hit=("snaps with quick jaws", "darts in for a hamstring bite"),
        flavor_miss=("circles wide and yips", "feints away"),
    ),
    "peaks_marten": EnemyDef(
        id="peaks_marten", name="alpine marten", zone="peaks", glyph="m",
        hp=38, atk=10, def_=4, spd=14, xp_reward=15,
        flavor_hit=("dives from a snow shelf", "rakes with needle claws"),
        flavor_miss=("vanishes between rocks", "feints and slips"),
    ),
    "peaks_snow_leopard": EnemyDef(
        id="peaks_snow_leopard", name="snow leopard", zone="peaks", glyph="L",
        hp=58, atk=14, def_=8, spd=11, xp_reward=20,
        flavor_hit=("pounces from a ledge", "rakes with a forepaw"),
        flavor_miss=("vanishes into the snow", "slinks behind a boulder"),
    ),
    # ─── tundra (Lv 12+) ────────────────────────────────────────────────────
    "tundra_arctic_fox": EnemyDef(
        id="tundra_arctic_fox", name="arctic fox", zone="tundra", glyph="f",
        hp=58, atk=14, def_=6, spd=14, xp_reward=22,
        flavor_hit=("dives at a hindleg", "snaps with frost-rimed teeth"),
        flavor_miss=("vanishes into the white", "feints across the drift"),
    ),
    "tundra_wolverine": EnemyDef(
        id="tundra_wolverine", name="wolverine", zone="tundra", glyph="W",
        hp=78, atk=18, def_=10, spd=10, xp_reward=28,
        flavor_hit=("clamps with crushing jaws", "drives in claws-first"),
        flavor_miss=("growls and circles", "skids on packed snow"),
    ),
    "tundra_polar_bear": EnemyDef(
        id="tundra_polar_bear", name="polar bear", zone="tundra", glyph="B",
        hp=110, atk=22, def_=14, spd=8, xp_reward=38,
        flavor_hit=("crashes a paw down", "drags forward with terrible weight"),
        flavor_miss=("misjudges the lunge", "shakes a frozen crust off its ruff"),
    ),
    # ─── abyss (Lv 15+) ─────────────────────────────────────────────────────
    "abyss_viperfish": EnemyDef(
        id="abyss_viperfish", name="viperfish", zone="abyss", glyph="v",
        hp=66, atk=18, def_=6, spd=12, xp_reward=26,
        flavor_hit=("snaps with curved fangs", "lunges with luminous teeth bared"),
        flavor_miss=("dissolves into the dark", "circles wide on a current"),
    ),
    "abyss_giant_isopod": EnemyDef(
        id="abyss_giant_isopod", name="abyssal giant isopod", zone="abyss", glyph="#",
        hp=92, atk=14, def_=18, spd=4, xp_reward=30,
        flavor_hit=("clamps an armored mandible", "rolls and slams"),
        flavor_miss=("scrapes uselessly off plate", "tucks defensively"),
    ),
    "abyss_dunkleosteus": EnemyDef(
        id="abyss_dunkleosteus", name="dunkleosteus", zone="abyss", glyph="D",
        hp=140, atk=26, def_=18, spd=10, xp_reward=46,
        flavor_hit=("shears with bone-plate jaws", "drives forward like a battering ram"),
        flavor_miss=("overshoots in the gloom", "circles back through the dark"),
    ),
}


ZONE_ENEMIES: dict[str, tuple[str, ...]] = {
    "forest": ("forest_spiderling", "forest_wasp", "forest_centipede", "forest_viper"),
    "cave": ("cave_bat", "cave_olm", "cave_isopod", "cave_angler", "cave_centipede", "cave_crayfish"),
    "ruins": ("ruins_packrat", "ruins_scorpion", "ruins_swift", "ruins_rattlesnake", "ruins_jackal"),
    "peaks": ("peaks_ermine", "peaks_raptor", "peaks_andean_condor", "peaks_marten", "peaks_snow_leopard"),
    "tundra": ("tundra_arctic_fox", "tundra_wolverine", "tundra_polar_bear"),
    "abyss": ("abyss_viperfish", "abyss_giant_isopod", "abyss_dunkleosteus"),
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


_LEGACY_ENEMY_IDS: dict[str, str] = {
    # Naturalization rename pass: old fantasy enemy ids resolve to their
    # real-species replacements so an in-flight Combat survives the rename.
    "forest_thornling": "forest_centipede",
    "cave_slime": "cave_olm",
    "cave_crawler": "cave_isopod",
    "ruins_wight": "ruins_packrat",
    "ruins_ward": "ruins_scorpion",
    "ruins_echo": "ruins_swift",
    "peaks_frostling": "peaks_ermine",
    "peaks_wyvern": "peaks_andean_condor",
}


def get_enemy(enemy_id: str) -> EnemyDef:
    enemy_id = _LEGACY_ENEMY_IDS.get(enemy_id, enemy_id)
    if enemy_id not in ENEMIES:
        raise KeyError(f"unknown enemy: {enemy_id!r}")
    return ENEMIES[enemy_id]


# ─── enemy sprites ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EnemySprite:
    """Idle / attack / hurt frame banks for an enemy. Idle is required;
    attack and hurt fall back to idle when missing.
    """
    idle: tuple[tuple[str, ...], ...]
    attack: tuple[tuple[str, ...], ...]
    hurt: tuple[tuple[str, ...], ...]


_ENEMY_SPRITE_CACHE: dict[str, EnemySprite] = {}


def _glyph_fallback_sprite(enemy: EnemyDef) -> EnemySprite:
    """Single-frame fallback when a sprite file is missing — render the
    glyph centred in a small box so the pane has something to draw.
    """
    frame = (
        "      ",
        f"  {enemy.glyph}   ",
        "      ",
    )
    bank = (frame,)
    return EnemySprite(idle=bank, attack=bank, hurt=bank)


def get_enemy_sprite(enemy_id: str) -> EnemySprite:
    """Return cached enemy sprite, loading from sprites/enemies/<id>.txt.
    Falls back to a glyph-only sprite if the file is missing or empty.
    """
    if enemy_id in _ENEMY_SPRITE_CACHE:
        return _ENEMY_SPRITE_CACHE[enemy_id]
    enemy = get_enemy(enemy_id)
    path = paths.enemy_sprites_dir() / f"{enemy_id}.txt"
    if not path.exists():
        sprite = _glyph_fallback_sprite(enemy)
        _ENEMY_SPRITE_CACHE[enemy_id] = sprite
        return sprite
    parsed = _parse_sprite_file(path.read_text())
    if not parsed.idle_frames:
        sprite = _glyph_fallback_sprite(enemy)
        _ENEMY_SPRITE_CACHE[enemy_id] = sprite
        return sprite

    def _freeze(frames: list[list[str]]) -> tuple[tuple[str, ...], ...]:
        return tuple(tuple(f) for f in frames)

    idle = _freeze(parsed.idle_frames)
    attack = _freeze(parsed.attack_frames) or idle
    hurt = _freeze(parsed.hurt_frames) or idle
    sprite = EnemySprite(idle=idle, attack=attack, hurt=hurt)
    _ENEMY_SPRITE_CACHE[enemy_id] = sprite
    return sprite


def _push_log(combat: Combat, line: str) -> None:
    combat.log.append(line)
    if len(combat.log) > LOG_CAP:
        combat.log = combat.log[-LOG_CAP:]


def _apply_status_application_chance(buddy: Buddy, base_pct: int) -> int:
    """% chance an applier with `base_pct` actually lands a status on `buddy`,
    after subtracting RES-based resistance. `mind_ward` doubles RES contribution.
    Floors at 5% so resistant buddies aren't immune.
    """
    res_resist = buddy.stats.res * 2
    if skills.is_engaged(buddy, "mind_ward"):
        res_resist *= 2
    res_resist = min(60, res_resist)
    return max(5, base_pct - res_resist)


def _tick_poison_on(side: str, combat: Combat, buddy: Buddy, name: str) -> Optional[int]:
    """If `side` ('buddy' or 'enemy') is poisoned, deal one tick of damage
    and decrement strikes_left. Returns dmg dealt or None if no poison.

    Buddy poison floors HP at 1 — same convention as `_enemy_attack`.
    """
    if side == "enemy":
        if combat.enemy_poison_strikes_left <= 0:
            return None
        dmg = combat.enemy_poison_dmg
        combat.enemy_hp = max(0, combat.enemy_hp - dmg)
        combat.enemy_poison_strikes_left -= 1
        if combat.enemy_poison_strikes_left == 0:
            combat.enemy_poison_dmg = 0
        _push_log(combat, f"{name} suffers from poison (-{dmg})")
        return dmg
    if combat.buddy_poison_strikes_left <= 0:
        return None
    dmg = combat.buddy_poison_dmg
    buddy.current_hp = max(1, buddy.current_hp - dmg)
    combat.buddy_poison_strikes_left -= 1
    if combat.buddy_poison_strikes_left == 0:
        combat.buddy_poison_dmg = 0
    _push_log(combat, f"{name} suffers from poison (-{dmg})")
    return dmg


def _strike_interval(spd: int) -> int:
    """Per-strike cooldown (whole seconds) for an attacker with this SPD.

    Inverse-linear scaling against BASELINE_SPD: spd 10 → 3s, spd 20 → 2s
    (clamped), spd 5 → 6s. Clamped to [MIN, MAX] so extremes stay sane.
    """
    if spd <= 0:
        return MAX_STRIKE_INTERVAL_S
    raw = BASE_STRIKE_INTERVAL_S * BASELINE_SPD / spd
    return int(round(max(MIN_STRIKE_INTERVAL_S, min(MAX_STRIKE_INTERVAL_S, raw))))


# ─── spawn / tick ───────────────────────────────────────────────────────────

def pick_enemy_for_quest(qdef: QuestDef, buddy: Buddy, rng: random.Random) -> Optional[EnemyDef]:
    """Pick a zone enemy, weighting lure-tagged enemies higher when the
    buddy's INT is too low to see through the bait.
    """
    zone = _quest_zone(qdef)
    if zone is None:
        return None
    pool = ZONE_ENEMIES.get(zone, ())
    if not pool:
        return None
    weights: list[int] = []
    for eid in pool:
        e = ENEMIES[eid]
        if e.lure > 0:
            edge = max(0, e.lure - buddy.stats.int_ // LURE_INT_DIVISOR)
            weights.append(1 + edge)
        else:
            weights.append(1)
    chosen_id = rng.choices(list(pool), weights=weights, k=1)[0]
    return ENEMIES[chosen_id]


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
    # Evade: chance-based, MP-gated. INT raises the avoid chance up to a 75%
    # cap. MP is only consumed on a successful dodge — failed rolls are free.
    if skills.has_active(buddy, "evade") and buddy.current_mana >= EVADE_MANA_COST:
        avoid_chance = min(EVADE_CAP, EVADE_BASE_PCT + buddy.stats.int_ * EVADE_INT_SCALE)
        if rng.random() < avoid_chance:
            buddy.current_mana -= EVADE_MANA_COST
            return False
    enemy = pick_enemy_for_quest(qdef, buddy, rng)
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

    # ORDER MATTERS: the engagement loop MUST run after Combat() creation
    # (engaged_skills are stored on the Combat object) and BEFORE the lure
    # ambush + buddy ambush (which read engaged_skills for skill effects).
    # Engagement: fight-wide active skills attempt to pay their MP cost.
    # Successfully-paid skills go into combat.engaged_skills and apply for
    # the duration of this encounter. Skills that can't pay are silently
    # left out. One-shot skills (ambush, second_wind, swift_escape) have
    # their own pay-on-fire path and are intentionally not engaged here.
    for sid in list(buddy.active_skills):
        sk = skills.SKILLS.get(sid)
        if sk is None or not skills.is_engagement_skill(sk):
            continue
        if sk.mana_cost <= 0:
            buddy.combat.engaged_skills.append(sid)
            continue
        if buddy.current_mana >= sk.mana_cost:
            buddy.current_mana -= sk.mana_cost
            buddy.combat.engaged_skills.append(sid)

    # Lure trait: the enemy baited the buddy in and gets a free pre-emptive
    # strike. Pushes the enemy's regular cadence so it doesn't double-tap.
    if enemy.lure > 0:
        _push_log(buddy.combat, f"the {enemy.name} lured {buddy.name} in!")
        dmg, hit = _enemy_attack(buddy, enemy, rng)
        if hit and dmg > 0:
            buddy.current_hp = max(1, buddy.current_hp - dmg)
            _push_log(buddy.combat, f"{enemy.name} ambushes for {dmg}!")
        elif hit:
            _push_log(buddy.combat, f"{enemy.name}'s ambush — deflected!")
        else:
            _push_log(buddy.combat, f"{enemy.name}'s ambush whiffs")
        buddy.combat.last_attacker = "enemy"
        buddy.combat.next_enemy_strike_at = now + _strike_interval(enemy.spd)

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
      - rampage: +1 base damage per landed strike during this encounter, capped at +5
    """
    extra_crit_pct = skills.get_combat_modifier(buddy, "crit_chance") / 100.0
    crit_cap = 0.35 + extra_crit_pct
    crit_chance = min(crit_cap, 0.05 + buddy.stats.luck * 0.01 + extra_crit_pct)
    crit = rng.random() < crit_chance
    base = max(1, buddy.stats.atk - enemy.def_ + rng.randint(-1, 1))
    if (
        buddy.combat is not None
        and buddy.combat.enemy_hp == buddy.combat.enemy_max_hp
        and skills.is_engaged(buddy, "battle_cry")
    ):
        base += 3
    if buddy.combat is not None and skills.is_engaged(buddy, "rampage"):
        base += min(5, buddy.combat.rampage_stacks)
    exec_flat, exec_crit_pct = skills.get_execute_bonus(buddy, buddy.combat)
    base += exec_flat
    if crit:
        crit_bonus = buddy.stats.atk // 2 + 1 + skills.get_crit_bonus(buddy)
        if exec_crit_pct:
            crit_bonus = crit_bonus * (100 + exec_crit_pct) // 100
        base += crit_bonus
    return base, crit


def _enemy_attack(buddy: Buddy, enemy: EnemyDef, rng: random.Random) -> tuple[int, bool]:
    """Return (damage_dealt, hit?). Enemy whiffs occasionally based on buddy spd.

    Three-state output:
      - hit=False, dmg=0  → swing missed entirely (flavor_miss line)
      - hit=True,  dmg=0  → contact made but DEF fully absorbed it (deflect)
      - hit=True,  dmg>0  → landing blow
    """
    # SPD-vs-enemy advantage grants a modest miss bonus (1pp per point), and
    # the explicit `dodge` skill stacks on top. Cap keeps the total whiff
    # chance from running away — fast attackers should pay out mainly through
    # strike cadence, not through becoming untouchable.
    spd_diff = max(0, buddy.stats.spd - enemy.spd)
    hit_threshold = min(DODGE_CAP, DODGE_MISS_BASE + spd_diff * DODGE_SPD_SCALE + skills.get_dodge_bonus(buddy))
    hit = rng.random() >= hit_threshold
    if not hit:
        return 0, False
    dmg = max(
        0,
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
    if not skills.is_engaged(buddy, "lucky_find"):
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

    IMPORTANT — stale-reference pattern: `combat` is cached locally from
    `buddy.combat` below. Inner strike functions (strike_buddy, strike_enemy)
    set `buddy.combat = None` on BUDDY_WIN, BUDDY_DOWN, or swift_escape.
    After those calls, only read from the local `combat` variable — NOT from
    `buddy.combat` which may be None. Any new code added between a strike
    call and the function return MUST use the local `combat` ref.
    """
    combat = buddy.combat
    if combat is None:
        return TickResult.WAITING
    try:
        enemy = get_enemy(combat.enemy_id)
    except KeyError:
        buddy.combat = None
        return TickResult.BUDDY_WIN  # enemy definition missing — treat as clear

    # Safety valve: force escape if the fight has dragged on past the cap.
    # Prevents infinite stalls from extreme stat mismatches.
    if now - combat.started_at > MAX_COMBAT_DURATION_S:
        _push_log(combat, f"{buddy.name} retreats from an endless fight!")
        buddy.combat = None
        return TickResult.ONGOING

    buddy_iv = _strike_interval(buddy.stats.spd)
    enemy_iv = _strike_interval(enemy.spd)

    # First-tick init: the side with higher spd opens immediately, the
    # other side has to wait its first interval.
    if combat.next_buddy_strike_at == 0:
        offset = 0 if buddy.stats.spd >= enemy.spd else buddy_iv
        combat.next_buddy_strike_at = combat.started_at + offset
    if combat.next_enemy_strike_at == 0:
        offset = 0 if enemy.spd > buddy.stats.spd else enemy_iv
        combat.next_enemy_strike_at = combat.started_at + offset

    buddy_ready = now >= combat.next_buddy_strike_at
    enemy_ready = now >= combat.next_enemy_strike_at
    if not buddy_ready and not enemy_ready:
        return TickResult.WAITING

    # Whoever's next-strike-at is earliest goes first. Ties break on the
    # shorter overall interval (i.e. the genuinely faster attacker).
    if buddy_ready and (
        not enemy_ready
        or combat.next_buddy_strike_at < combat.next_enemy_strike_at
        or (combat.next_buddy_strike_at == combat.next_enemy_strike_at and buddy_iv <= enemy_iv)
    ):
        next_attacker = "buddy"
    else:
        next_attacker = "enemy"

    combat.last_round_at = now

    # Status tick: the side about to act takes any poison damage first. A
    # poison tick that drops the enemy to 0 HP wins the fight outright; a
    # buddy poison tick floors at 1 HP and leaves the reaction chain to the
    # following enemy strike.
    if next_attacker == "enemy":
        _tick_poison_on("enemy", combat, buddy, enemy.name)
        if combat.enemy_hp <= 0:
            buddy.xp += enemy.xp_reward
            _push_log(combat, f"{enemy.name} is defeated (+{enemy.xp_reward} xp)")
            _roll_lucky_find(buddy, qdef, rng)
            _roll_mana_siphon(buddy)
            buddy.combat = None
            return TickResult.BUDDY_WIN
    else:
        _tick_poison_on("buddy", combat, buddy, buddy.name)

    def strike_buddy() -> Optional[TickResult]:
        combat.last_attacker = "buddy"
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
        # Rampage: stack +1 per landed buddy strike. Cap is enforced in
        # _buddy_attack's read so bumping past 5 here is harmless but tidy.
        combat.rampage_stacks = min(5, combat.rampage_stacks + 1)
        # Double Strike: free same-tick follow-up while the enemy is alive.
        if skills.is_engaged(buddy, "double_strike") and rng.random() < 0.25:
            dmg2, crit2 = _buddy_attack(buddy, enemy, rng)
            combat.enemy_hp = max(0, combat.enemy_hp - dmg2)
            _push_log(combat, f"{buddy.name} strikes again for {dmg2}!")
            if combat.enemy_hp <= 0:
                buddy.xp += enemy.xp_reward
                _push_log(combat, f"{enemy.name} is defeated (+{enemy.xp_reward} xp)")
                _roll_lucky_find(buddy, qdef, rng)
                _roll_mana_siphon(buddy)
                buddy.combat = None
                return TickResult.BUDDY_WIN
            combat.rampage_stacks = min(5, combat.rampage_stacks + 1)
        # Venom Fang: chance to poison the enemy. Scales with INT, no
        # stacking (the enemy is either poisoned or not).
        if (
            skills.is_engaged(buddy, "venom_fang")
            and combat.enemy_poison_strikes_left == 0
        ):
            apply_pct = min(VENOM_CAP_PCT, VENOM_BASE_PCT + buddy.stats.int_ // VENOM_INT_SCALE_DIV)
            if rng.random() * 100 < apply_pct:
                combat.enemy_poison_dmg = VENOM_DAMAGE
                combat.enemy_poison_strikes_left = VENOM_DURATION
                _push_log(combat, f"{buddy.name} envenoms the {enemy.name}!")
        return None

    def strike_enemy() -> Optional[TickResult]:
        combat.last_attacker = "enemy"
        dmg, hit = _enemy_attack(buddy, enemy, rng)
        if not hit:
            _push_log(combat, f"{enemy.name} {rng.choice(enemy.flavor_miss)}")
            return None
        if dmg == 0:
            # Hit landed but DEF (and skills like stoneblood / bulwark) absorbed
            # it completely. Counter still fires — contact is contact — but the
            # buddy takes no HP damage and the brink-reaction chain is skipped.
            _push_log(combat, f"{enemy.name} {rng.choice(enemy.flavor_hit)} — deflected!")
        else:
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
        # Reflect Thorns: every contact-attempt (hit, deflect, miss) returns
        # a flat RES//4 damage to the attacker.
        if skills.is_engaged(buddy, "reflect_thorns"):
            thorn_dmg = max(1, buddy.stats.res // THORN_RES_DIVISOR)
            combat.enemy_hp = max(0, combat.enemy_hp - thorn_dmg)
            _push_log(combat, f"{enemy.name} grazes thorns (-{thorn_dmg})")
            if combat.enemy_hp <= 0:
                buddy.xp += enemy.xp_reward
                _push_log(combat, f"{enemy.name} is defeated (+{enemy.xp_reward} xp)")
                _roll_lucky_find(buddy, qdef, rng)
                _roll_mana_siphon(buddy)
                buddy.combat = None
                return TickResult.BUDDY_WIN
        if dmg > 0 and buddy.current_hp <= 1:
            # Reaction chain: second_wind keeps you fighting, swift_escape
            # flees cleanly, otherwise BUDDY_DOWN fails the quest. Only fires
            # when the buddy actually took damage this tick — a deflected hit
            # at 1 HP does NOT burn second_wind.
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

    fn = strike_buddy if next_attacker == "buddy" else strike_enemy
    outcome = fn()
    # Push that side's next-strike-at forward by their interval. Counters
    # fired inside strike_enemy are reactive and intentionally don't
    # consume the buddy's regular cadence.
    if next_attacker == "buddy":
        combat.next_buddy_strike_at = now + buddy_iv
    elif buddy.combat is not None:
        combat.next_enemy_strike_at = now + enemy_iv
    if outcome is not None:
        return outcome
    return TickResult.ONGOING
