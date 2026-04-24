"""Quest registry, zones, smart selection, rolls, and flavor text."""
from __future__ import annotations

import random
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import skills, species, vignettes
from llm import extract_json_object as _extract_json_object
from state import Buddy, Quest, State


MANA_CAST_COST = 10
MANA_BOOST = 0.25


@dataclass
class IdleDecision:
    """One step the activity loop may take on a given tick.

    Shared by the `claude -p` path (constructed from parsed JSON) and
    the fallback `pick_for_idle` dice path.
    """
    action: str  # "noop" | "idle_flavor" | "start_quest"
    quest_id: Optional[str] = None
    flavor: Optional[str] = None
    reason: str = ""


@dataclass(frozen=True)
class QuestDef:
    id: str
    name: str
    duration_s: int
    difficulty: int  # tuning knob for success probability
    key_stats: tuple[str, ...]  # stat attr names on Stats dataclass
    xp_success_range: tuple[int, int]
    xp_failure: int
    items_on_success: tuple[str, ...]
    hp_penalty_pct_on_failure: int
    blurb: str
    flavor: tuple[str, ...]
    category: str  # "combat" | "gathering" | "rest" — no default; must be explicit


@dataclass(frozen=True)
class Zone:
    id: str
    name: str
    recommended_level: int
    blurb: str
    quest_ids: tuple[str, ...]


QUESTS: dict[str, QuestDef] = {
    # ─── meadow (starter, Lv 1) ─────────────────────────────────────────────
    "meadow_butterfly": QuestDef(
        id="meadow_butterfly", name="Butterfly Chase", duration_s=90, difficulty=3,
        key_stats=("spd", "luck"),
        xp_success_range=(15, 25), xp_failure=4,
        items_on_success=("dew-drop",), hp_penalty_pct_on_failure=0,
        blurb="Zig-zag through tall grass after a cabbage white.",
        flavor=(
            "pounces at a butterfly and misses",
            "sneezes from loose pollen",
            "tumbles through tall grass",
            "locks eyes with a ladybug",
            "freezes mid-step as a wing flickers past",
            "skids on a clover patch chasing a flash of white",
            "stops to track a second butterfly that wasn't there",
            "leaps after a shadow and lands gracefully on grass",
        ),
        category="gathering",
    ),
    "meadow_pollen": QuestDef(
        id="meadow_pollen", name="Pollen Gathering", duration_s=150, difficulty=5,
        key_stats=("int_", "luck"),
        xp_success_range=(20, 35), xp_failure=5,
        items_on_success=("pollen-sack",), hp_penalty_pct_on_failure=0,
        blurb="Carefully brush pollen off obliging wildflowers.",
        flavor=(
            "ponders which flower is best",
            "carefully sidesteps a bumblebee",
            "carries a neat little pollen bundle",
            "stops to admire a daisy",
            "shakes a stamen and sneezes yellow",
            "negotiates politely with a hovering bee",
            "tucks pollen into a fur-pocket on its shoulder",
            "rolls in a buttercup and emerges glowing",
        ),
        category="gathering",
    ),
    "meadow_rabbit": QuestDef(
        id="meadow_rabbit", name="Rabbit Tracking", duration_s=180, difficulty=7,
        key_stats=("spd", "atk"),
        xp_success_range=(30, 50), xp_failure=6,
        items_on_success=("rabbit-tuft",), hp_penalty_pct_on_failure=0,
        blurb="Trail a startled hare across the open field.",
        flavor=(
            "sprints through a patch of clover",
            "loses the trail, then finds it again",
            "spots a warren and hesitates",
            "leaps over a fallen branch",
            "freezes — then bolts after a flash of brown",
            "noses at a fresh print and grins",
            "doubles back to check a snapped grass blade",
            "skids to a stop, ears swivelling",
        ),
        category="gathering",
    ),

    # ─── forest (Lv 3) ──────────────────────────────────────────────────────
    "forest_forage": QuestDef(
        id="forest_forage", name="Mushroom Forage", duration_s=180, difficulty=9,
        key_stats=("int_", "luck"),
        xp_success_range=(45, 70), xp_failure=10,
        items_on_success=("mushroom-cap",), hp_penalty_pct_on_failure=5,
        blurb="Pick through moss for the good mushrooms, not the bad ones.",
        flavor=(
            "eyes a suspicious red cap",
            "nibbles a leaf to be sure",
            "digs up a promising stem",
            "backs away from a slime mold",
            "double-checks a spore print against memory",
            "brushes loam off a fat brown cap",
            "sniffs a mushroom and decides yes",
            "stacks three caps neatly at the trunk",
        ),
        category="combat",
    ),
    "forest_sapling": QuestDef(
        id="forest_sapling", name="Lost Sapling", duration_s=240, difficulty=11,
        key_stats=("int_", "spd"),
        xp_success_range=(55, 85), xp_failure=12,
        items_on_success=("sapling-charm",), hp_penalty_pct_on_failure=5,
        blurb="A rare sapling has gone missing from its grove. Find it.",
        flavor=(
            "sniffs around mossy roots",
            "hears distant rustling",
            "double-checks a hollow log",
            "follows a trail of acorns",
            "kneels by a footprint that isn't quite right",
            "circles a stump that hums faintly",
            "untangles a leafless twig from its tail",
            "whispers a question to the canopy",
        ),
        category="combat",
    ),
    "forest_spider": QuestDef(
        id="forest_spider", name="Spider Hollow", duration_s=300, difficulty=14,
        key_stats=("atk", "spd"),
        xp_success_range=(70, 100), xp_failure=15,
        items_on_success=("silk-strand",), hp_penalty_pct_on_failure=5,
        blurb="Something eight-legged has been stringing up the deer paths.",
        flavor=(
            "sidesteps a low-hanging web",
            "spots glinting eyes in a hollow",
            "stomps on an advance scout",
            "swats a strand of silk",
            "ducks under a glistening trip-line",
            "tracks rustling along the canopy above",
            "crushes a twitching egg-sac under one paw",
            "flicks silk from its whiskers and growls",
        ),
        category="combat",
    ),

    # ─── cave (Lv 5) ────────────────────────────────────────────────────────
    "cave_crystals": QuestDef(
        id="cave_crystals", name="Glow-Crystal Mine", duration_s=360, difficulty=14,
        key_stats=("def_", "int_"),
        xp_success_range=(85, 125), xp_failure=18,
        items_on_success=("glow-crystal",), hp_penalty_pct_on_failure=10,
        blurb="Pry luminous shards from a crumbling wall without bringing it down.",
        flavor=(
            "taps a wall, listening for hollows",
            "pockets a pulsing shard",
            "dodges a slow rockfall",
            "squints at a vein in the rock",
        ),
        category="combat",
    ),
    "cave_river": QuestDef(
        id="cave_river", name="Underground River", duration_s=300, difficulty=16,
        key_stats=("spd", "res"),
        xp_success_range=(95, 140), xp_failure=20,
        items_on_success=("river-pearl",), hp_penalty_pct_on_failure=10,
        blurb="Ford a bone-cold stream running through the dark.",
        flavor=(
            "slips on a wet stone",
            "catches a glimpse of something pale",
            "wades knee-deep in icy water",
            "shakes water from its fur",
        ),
        category="combat",
    ),
    "cave_echoes": QuestDef(
        id="cave_echoes", name="Echo Chamber", duration_s=420, difficulty=20,
        key_stats=("res", "int_"),
        xp_success_range=(115, 165), xp_failure=24,
        items_on_success=("echo-stone",), hp_penalty_pct_on_failure=10,
        blurb="A vast, resonant cave where voices come back wrong.",
        flavor=(
            "hears its own name whispered",
            "stops, unsure which way is forward",
            "clamps paws over ears",
            "listens for a different echo",
        ),
        category="combat",
    ),

    # ─── ruins (Lv 7) ───────────────────────────────────────────────────────
    "ruins_vault": QuestDef(
        id="ruins_vault", name="Sealed Vault", duration_s=480, difficulty=20,
        key_stats=("def_", "res"),
        xp_success_range=(150, 210), xp_failure=30,
        items_on_success=("vault-token",), hp_penalty_pct_on_failure=15,
        blurb="A stone vault in a forgotten temple, still sealed shut.",
        flavor=(
            "tests a rusted hinge",
            "feels for a hidden latch",
            "wedges open a cracked lid",
            "grits its teeth and shoves",
        ),
        category="combat",
    ),
    "ruins_codex": QuestDef(
        id="ruins_codex", name="Sealed Codex", duration_s=420, difficulty=22,
        key_stats=("int_", "luck"),
        xp_success_range=(160, 225), xp_failure=32,
        items_on_success=("codex-page",), hp_penalty_pct_on_failure=15,
        blurb="An inscribed stone book whose pages stick together with age.",
        flavor=(
            "scratches its head at the script",
            "pries two pages apart, very gently",
            "steps back to study the layout",
            "smudges an ink line and winces",
        ),
        category="combat",
    ),
    "ruins_collapse": QuestDef(
        id="ruins_collapse", name="Collapsing Vault", duration_s=600, difficulty=26,
        key_stats=("atk", "res", "def_"),
        xp_success_range=(190, 270), xp_failure=36,
        items_on_success=("relic-fragment",), hp_penalty_pct_on_failure=15,
        blurb="The floor is giving out — get the artifact before the ceiling does.",
        flavor=(
            "tests a sagging beam",
            "ducks a falling shard",
            "dives clear of a dropping slab",
            "braces against a tremor",
        ),
        category="combat",
    ),

    # ─── peaks (Lv 10, endgame) ─────────────────────────────────────────────
    "peaks_climb": QuestDef(
        id="peaks_climb", name="Mountain Climb", duration_s=720, difficulty=25,
        key_stats=("spd", "luck", "res"),
        xp_success_range=(230, 310), xp_failure=40,
        items_on_success=("summit-stone",), hp_penalty_pct_on_failure=25,
        blurb="Up, up, through thin air and sudden gusts.",
        flavor=(
            "grips a frost-slick handhold",
            "squints through the wind",
            "pulls itself onto a narrow ledge",
            "catches its breath in thin air",
        ),
        category="combat",
    ),
    "peaks_bear": QuestDef(
        id="peaks_bear", name="Cave Bear Encounter", duration_s=900, difficulty=30,
        key_stats=("atk", "def_", "res"),
        xp_success_range=(270, 370), xp_failure=48,
        items_on_success=("bear-pelt",), hp_penalty_pct_on_failure=25,
        blurb="A cave bear has made a den of the upper pass.",
        flavor=(
            "shivers under a baleful glare",
            "ducks a swinging paw",
            "skids across packed snow",
            "finds a bad place to stand",
        ),
        category="combat",
    ),
    "peaks_condor": QuestDef(
        id="peaks_condor", name="Andean Condor", duration_s=1200, difficulty=35,
        key_stats=("atk", "def_", "spd", "int_"),
        xp_success_range=(330, 460), xp_failure=55,
        items_on_success=("condor-feather",), hp_penalty_pct_on_failure=25,
        blurb="An Andean condor — ten-foot wingspan and meaner than it looks.",
        flavor=(
            "circles warily, watching the wingspan",
            "dives under a dropped stone",
            "lands a glancing blow on a wing",
            "rolls clear of stooping talons",
            "howls a battle cry",
        ),
        category="combat",
    ),

    # ─── gathering (non-combat, HP never at risk) ───────────────────────────
    "meadow_berry_forage": QuestDef(
        id="meadow_berry_forage", name="Berry Forage", duration_s=120, difficulty=2,
        key_stats=("luck", "int_"),
        xp_success_range=(10, 16), xp_failure=3,
        items_on_success=("wild-berry",), hp_penalty_pct_on_failure=0,
        blurb="Pluck ripe berries from low brambles in the meadow edge.",
        flavor=(
            "tastes a berry and immediately spits it out",
            "finds a perfect cluster of ripe fruit",
            "carries three berries stacked on its back",
            "hums while picking",
            "untangles a thorn from one ear",
            "stains its paws purple and admires the color",
            "compares two berries and picks the larger one",
            "sneaks a snack while no one is looking",
        ),
        category="gathering",
    ),
    "meadow_dew_collect": QuestDef(
        id="meadow_dew_collect", name="Dew Collection", duration_s=90, difficulty=2,
        key_stats=("int_",),
        xp_success_range=(8, 14), xp_failure=2,
        items_on_success=("dew-drop",), hp_penalty_pct_on_failure=0,
        blurb="Tilt grass blades into a little cup and catch the morning dew.",
        flavor=(
            "tilts a grass blade with great concentration",
            "watches a drop roll and catches it",
            "spills half the dew on its paws",
            "admires the tiny rainbow in a droplet",
            "balances a fat dewdrop on a leaf-tip",
            "licks a stray drop off its own nose",
            "wipes a paw on the grass and tries again",
            "sighs at a perfect drop, lost",
        ),
        category="gathering",
    ),
    "forest_moss_gather": QuestDef(
        id="forest_moss_gather", name="Moss Gather", duration_s=180, difficulty=3,
        key_stats=("int_", "luck"),
        xp_success_range=(14, 22), xp_failure=4,
        items_on_success=("moss-clump",), hp_penalty_pct_on_failure=0,
        blurb="Comb soft green moss off north-facing stones in the understory.",
        flavor=(
            "prods at a patch of soft moss",
            "smells the moss and sneezes",
            "finds a perfect velvety clump",
            "listens to the forest and picks carefully",
            "rolls a clump of moss into a tidy ball",
            "picks moss out from between its toes",
            "tests a soft patch with one careful claw",
            "tucks a green tuft behind one ear",
        ),
        category="gathering",
    ),
    "cave_pebble_sort": QuestDef(
        id="cave_pebble_sort", name="Pebble Sorting", duration_s=150, difficulty=3,
        key_stats=("luck",),
        xp_success_range=(12, 18), xp_failure=3,
        items_on_success=("smooth-pebble",), hp_penalty_pct_on_failure=0,
        blurb="Sort smooth cave pebbles by size. Peaceful, almost meditative.",
        flavor=(
            "lines up pebbles by size, very seriously",
            "polishes a pebble on its fur",
            "makes a small pebble tower",
            "compares two pebbles with a thoughtful look",
        ),
        category="gathering",
    ),
    "meadow_sun_nap": QuestDef(
        id="meadow_sun_nap", name="Sun Nap", duration_s=60, difficulty=1,
        key_stats=("res",),
        xp_success_range=(4, 8), xp_failure=1,
        items_on_success=(), hp_penalty_pct_on_failure=0,
        blurb="Flop down in a patch of warm grass and close your eyes a while.",
        flavor=(
            "finds the sunniest patch of grass",
            "turns three times before settling down",
            "twitches its ear in a half-dream",
            "yawns so wide you can count the teeth",
        ),
        category="rest",
    ),

    # ─── tundra (Lv 12, high-tier) ──────────────────────────────────────────
    "tundra_burrow": QuestDef(
        id="tundra_burrow", name="Snow Burrow", duration_s=180, difficulty=12,
        key_stats=("res",),
        xp_success_range=(80, 120), xp_failure=20,
        items_on_success=(), hp_penalty_pct_on_failure=0,
        blurb="Curl up in a packed-snow hollow and wait out the wind.",
        flavor=(
            "scrapes a hollow in the drift",
            "tucks its nose under its tail",
            "listens to the wind whistle past",
            "warms its paws against its belly",
        ),
        category="rest",
    ),
    "tundra_lichen_pick": QuestDef(
        id="tundra_lichen_pick", name="Lichen Pick", duration_s=300, difficulty=28,
        key_stats=("int_", "luck"),
        xp_success_range=(220, 320), xp_failure=45,
        items_on_success=("frost-lichen",), hp_penalty_pct_on_failure=0,
        blurb="Pry crusty lichen off wind-blasted rocks. Worth the cold.",
        flavor=(
            "scrapes lichen off a frost-bitten boulder",
            "cups its breath to warm its paws",
            "compares two patches and picks the brighter one",
            "tucks a clump into a fur pouch",
        ),
        category="gathering",
    ),
    "tundra_seal_watch": QuestDef(
        id="tundra_seal_watch", name="Seal Pup Watch", duration_s=420, difficulty=32,
        key_stats=("int_", "spd"),
        xp_success_range=(280, 380), xp_failure=55,
        items_on_success=("seal-down",), hp_penalty_pct_on_failure=10,
        blurb="Track a seal nursery across the pack ice without spooking the pups.",
        flavor=(
            "lies flat behind a snow ridge",
            "marks a fresh slide trail",
            "freezes as a head pops up",
            "keeps downwind of the breathing holes",
        ),
        category="gathering",
    ),
    "tundra_wolverine": QuestDef(
        id="tundra_wolverine", name="Wolverine Standoff", duration_s=600, difficulty=36,
        key_stats=("atk", "def_", "res"),
        xp_success_range=(360, 480), xp_failure=72,
        items_on_success=("wolverine-pelt",), hp_penalty_pct_on_failure=25,
        blurb="A wolverine has claimed the carcass first. It is not in a sharing mood.",
        flavor=(
            "circles the kill warily",
            "ducks a snapping jaw",
            "lands a glancing rake",
            "skids on a frozen rib",
        ),
        category="combat",
    ),
    "tundra_polar_bear": QuestDef(
        id="tundra_polar_bear", name="Polar Bear Encounter", duration_s=900, difficulty=42,
        key_stats=("atk", "def_", "res", "hp"),
        xp_success_range=(440, 580), xp_failure=88,
        items_on_success=("bear-claw",), hp_penalty_pct_on_failure=30,
        blurb="A polar bear emerges from a fog bank. Nine hundred pounds, all teeth.",
        flavor=(
            "freezes in the bear's eyeline",
            "ducks under a paw the size of its head",
            "scrambles between ice floes",
            "lands a desperate strike",
            "bolts for cover behind a hummock",
        ),
        category="combat",
    ),

    # ─── abyss (Lv 15, deep ocean apex) ─────────────────────────────────────
    "abyss_drift": QuestDef(
        id="abyss_drift", name="Cold Current Drift", duration_s=240, difficulty=15,
        key_stats=("res",),
        xp_success_range=(110, 160), xp_failure=30,
        items_on_success=(), hp_penalty_pct_on_failure=0,
        blurb="Hang motionless in a deep cold current and let it carry you.",
        flavor=(
            "stops thrashing and lets the cold do its work",
            "slow-blinks in the dim glow",
            "drifts past a chain of jellies",
            "watches a marine snowfall settle",
        ),
        category="rest",
    ),
    "abyss_vent_sample": QuestDef(
        id="abyss_vent_sample", name="Hydrothermal Vent Sample", duration_s=480, difficulty=38,
        key_stats=("int_", "res"),
        xp_success_range=(380, 520), xp_failure=72,
        items_on_success=("tube-worm-fiber",), hp_penalty_pct_on_failure=15,
        blurb="Snip a fistful of tube worms from the lip of a black smoker. Don't get boiled.",
        flavor=(
            "skirts a curtain of superheated water",
            "snips at a tangle of tube worms",
            "ducks a sudden plume of mineral haze",
            "balances on a brittle chimney edge",
        ),
        category="gathering",
    ),
    "abyss_coral": QuestDef(
        id="abyss_coral", name="Black Coral Harvest", duration_s=540, difficulty=42,
        key_stats=("luck", "int_"),
        xp_success_range=(420, 560), xp_failure=80,
        items_on_success=("black-coral-shard",), hp_penalty_pct_on_failure=10,
        blurb="Cold-water black coral grows where light can't reach. Patient hands only.",
        flavor=(
            "kicks gently against a current",
            "saws at a single thick branch",
            "tucks a shard into a sealed pouch",
            "circles the colony to find the next cut",
        ),
        category="gathering",
    ),
    "abyss_giant_squid": QuestDef(
        id="abyss_giant_squid", name="Giant Squid Hunt", duration_s=900, difficulty=46,
        key_stats=("atk", "spd", "int_"),
        xp_success_range=(520, 680), xp_failure=100,
        items_on_success=("squid-beak",), hp_penalty_pct_on_failure=30,
        blurb="A giant squid pulses through the dark. Forty feet of arms and one cold eye.",
        flavor=(
            "tracks a flashing chromatophore",
            "ducks under a sweeping tentacle",
            "drives in for the mantle",
            "rolls clear of the hooked suckers",
        ),
        category="combat",
    ),
    "abyss_megalodon": QuestDef(
        id="abyss_megalodon", name="Megalodon Encounter", duration_s=1200, difficulty=55,
        key_stats=("atk", "def_", "spd", "res"),
        xp_success_range=(620, 820), xp_failure=125,
        items_on_success=("megalodon-tooth",), hp_penalty_pct_on_failure=35,
        blurb="A sixty-foot shark from the dark below. Probably regrettable.",
        flavor=(
            "feels the pressure wave first",
            "dives into a kelp tangle",
            "lands a glancing blow on a tooth",
            "rolls clear of the second pass",
            "pulses out a cloud of ink",
        ),
        category="combat",
    ),
}


ZONES: dict[str, Zone] = {
    "meadow": Zone(
        id="meadow", name="Meadow", recommended_level=1,
        blurb="Sun, grass, and nothing worse than a cranky bumblebee.",
        quest_ids=(
            "meadow_butterfly", "meadow_pollen", "meadow_rabbit",
            "meadow_berry_forage", "meadow_dew_collect", "meadow_sun_nap",
        ),
    ),
    "forest": Zone(
        id="forest", name="Forest", recommended_level=3,
        blurb="Deep woods where roots tangle and something rustles behind you.",
        quest_ids=("forest_forage", "forest_sapling", "forest_spider", "forest_moss_gather"),
    ),
    "cave": Zone(
        id="cave", name="Cave", recommended_level=5,
        blurb="Damp tunnels, dripping stalactites, and very little natural light.",
        quest_ids=("cave_crystals", "cave_river", "cave_echoes", "cave_pebble_sort"),
    ),
    "ruins": Zone(
        id="ruins", name="Ruins", recommended_level=7,
        blurb="Crumbling stonework where the wildlife has moved in. Watch your step.",
        quest_ids=("ruins_vault", "ruins_codex", "ruins_collapse"),
    ),
    "peaks": Zone(
        id="peaks", name="Peaks", recommended_level=10,
        blurb="Cold altitude, thin air, and the largest birds in the world circling overhead.",
        quest_ids=("peaks_climb", "peaks_bear", "peaks_condor"),
    ),
    "tundra": Zone(
        id="tundra", name="Tundra", recommended_level=12,
        blurb="Endless white. The wind has a list of things it will not return.",
        quest_ids=(
            "tundra_burrow", "tundra_lichen_pick", "tundra_seal_watch",
            "tundra_wolverine", "tundra_polar_bear",
        ),
    ),
    "abyss": Zone(
        id="abyss", name="Abyss", recommended_level=15,
        blurb="Pressure, dark, and creatures that have never seen the sun.",
        quest_ids=(
            "abyss_drift", "abyss_vent_sample", "abyss_coral",
            "abyss_giant_squid", "abyss_megalodon",
        ),
    ),
}


_LEGACY_IDS: dict[str, str] = {
    # Old flat quest ids from before the zone rework. If a buddy's state.json
    # still references one of these (from a mid-flight quest), resolve it to a
    # close equivalent in the new pool so claim_quest doesn't KeyError.
    "forest": "meadow_butterfly",
    "cave": "cave_crystals",
    "dragon": "peaks_condor",
    # Naturalization rename pass: old fantasy quest ids resolve to their
    # real-species replacements so any in-flight quest survives the rename.
    "peaks_yeti": "peaks_bear",
    "peaks_dragon": "peaks_condor",
    "ruins_guardian": "ruins_collapse",
    "ruins_runes": "ruins_codex",
}


def get(quest_id: str) -> QuestDef:
    quest_id = _LEGACY_IDS.get(quest_id, quest_id)
    if quest_id not in QUESTS:
        raise KeyError(f"unknown quest: {quest_id!r}")
    return QUESTS[quest_id]


def list_all() -> list[QuestDef]:
    return list(QUESTS.values())


def list_zones() -> list[Zone]:
    return list(ZONES.values())


def get_zone(zone_id: str) -> Zone:
    if zone_id not in ZONES:
        raise KeyError(f"unknown zone: {zone_id!r}")
    return ZONES[zone_id]


_FAIL_OUTROS: tuple[str, ...] = (
    "limped back empty-pawed",
    "retreated before things got worse",
    "called it a day and turned home",
    "gave up with a frustrated huff",
    "trudged back with nothing to show for it",
)


def _stat_score(buddy: Buddy, qdef: QuestDef) -> float:
    """Normalized relevant-stat score — matches the per-stat average used
    inside `_success_probability` (pre-skill bonuses)."""
    relevant = sum(getattr(buddy.stats, k) for k in qdef.key_stats)
    return relevant / max(1, len(qdef.key_stats))


def _weakest_key_stat(buddy: Buddy, qdef: QuestDef) -> Optional[str]:
    """Return the key_stat with the lowest raw buddy value, or None when the
    quest only has one key stat (no bottleneck worth reporting)."""
    if len(qdef.key_stats) < 2:
        return None
    return min(qdef.key_stats, key=lambda k: getattr(buddy.stats, k))


def _build_fail_narrative(
    buddy: Buddy, qdef: QuestDef, rng: random.Random,
) -> list[str]:
    """Pick 2 distinct mid-quest beats from qdef.flavor and append a retreat
    outro. Returns at most 3 lines; falls back gracefully when the flavor
    pool is empty or tiny.
    """
    pool = list(qdef.flavor) if qdef.flavor else []
    rng.shuffle(pool)
    picks = pool[:2]
    lines = [f"{buddy.name} {p}" for p in picks]
    lines.append(f"{buddy.name} {rng.choice(_FAIL_OUTROS)}.")
    return lines


def format_claim_event_line(result: "QuestResult", fired_names: list[str]) -> str:
    """Build the recent_events line for a quest claim result.

    Centralized here so server.py, activity_loop.py, and pane.py all
    produce identical formatting — change once, apply everywhere.
    """
    line = result.flavor
    if not result.success:
        hints: list[str] = [f"~{int(round(result.probability * 100))}% odds"]
        if result.weakest_stat:
            hints.append(f"{result.weakest_stat.rstrip('_')} was weakest")
        if result.defeated_by:
            hints.append(f"lost to a {result.defeated_by}")
        line += f" [{', '.join(hints)}]"
    line += (f" (+{result.xp} xp"
             + (f", got {', '.join(result.items)}" if result.items else "")
             + (f", -{result.hp_damage} hp" if result.hp_damage else "")
             + (f", cast -{result.mana_cost} mp" if result.mana_cast else "")
             + (f", used {', '.join(fired_names)}" if fired_names else "") + ")")
    return line


def _success_probability(buddy: Buddy, qdef: QuestDef) -> float:
    relevant = sum(getattr(buddy.stats, k) for k in qdef.key_stats)
    # Normalize by number of key stats so high-diff quests with more stats aren't doubly-penalized.
    score = relevant / max(1, len(qdef.key_stats)) + skills.flat_score_bonus(buddy, qdef)
    p = 0.5 + (score - qdef.difficulty) / 40
    return max(0.1, min(0.95, p))


_LLM_MODEL_ID = "claude-haiku-4-5-20251001"
_LLM_TIMEOUT_S = 30
_LLM_MAX_FAILURES = 3
_LLM_BACKOFF_S = 300  # skip LLM for 5 min after this many consecutive failures

_llm_failures = 0
_llm_backoff_until = 0.0



def _llm_fail() -> None:
    """Record an LLM call failure for the circuit breaker."""
    global _llm_failures, _llm_backoff_until
    _llm_failures += 1
    if _llm_failures >= _LLM_MAX_FAILURES:
        _llm_backoff_until = time.time() + _LLM_BACKOFF_S


def _pick_quest_via_llm(
    buddy: Buddy, zone_id: str, qdefs: list["QuestDef"],
) -> Optional[tuple["QuestDef", float]]:
    """Ask Claude to pick the quest the buddy feels most confident about.

    Returns (quest, probability) on success, None on any failure (missing
    binary, timeout, bad JSON, invalid quest_id). Caller falls back to
    the dice-based picker on None. A circuit breaker skips the LLM call
    entirely after _LLM_MAX_FAILURES consecutive failures.
    """
    global _llm_failures, _llm_backoff_until
    if _llm_failures >= _LLM_MAX_FAILURES and time.time() < _llm_backoff_until:
        return None  # circuit open
    claude_bin = shutil.which("claude")
    if not claude_bin:
        _llm_fail()
        return None

    quest_lines = []
    prob_map: dict[str, float] = {}
    qdef_map: dict[str, "QuestDef"] = {}
    for q in qdefs:
        p = _success_probability(buddy, q)
        prob_map[q.id] = p
        qdef_map[q.id] = q
        stats_display = ", ".join(k.rstrip("_") for k in q.key_stats)
        quest_lines.append(
            f"  - {q.id} \"{q.name}\" (diff {q.difficulty}, {q.duration_s}s, "
            f"stats: {stats_display}, success ~{int(round(p * 100))}%): {q.blurb}"
        )

    traits = buddy.traits or {}
    prompt = (
        f"You are deciding which quest an RPG pet should attempt.\n\n"
        f"Buddy: {buddy.name} the {buddy.species} (Lv{buddy.level}).\n"
        f"Stats: HP {buddy.stats.hp}, ATK {buddy.stats.atk}, DEF {buddy.stats.def_}, "
        f"SPD {buddy.stats.spd}, LUCK {buddy.stats.luck}, INT {buddy.stats.int_}, RES {buddy.stats.res}.\n"
        f"Personality: curiosity {traits.get('curiosity', 5)}, boldness {traits.get('boldness', 5)}, "
        f"patience {traits.get('patience', 5)}.\n\n"
        f"Available quests in {zone_id}:\n" + "\n".join(quest_lines) + "\n\n"
        f"Pick the quest this buddy would choose based on its stats and personality. "
        f"A cautious buddy picks safe quests; a bold buddy risks higher difficulty.\n"
        f"Reply with EXACTLY one JSON object: {{\"quest_id\": \"<id>\", \"reason\": \"<short sentence>\"}}\n"
    )

    system_prompt = (
        "You are a JSON-only decision oracle for an RPG pet game. "
        "Reply with EXACTLY one JSON object matching: "
        '{\"quest_id\": str, \"reason\": str}. '
        "No prose, no markdown, no code fences."
    )

    cmd = [
        claude_bin, "-p", prompt,
        "--system-prompt", system_prompt,
        "--setting-sources", "local",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--output-format", "text",
        "--model", _LLM_MODEL_ID,
        "--tools", "",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=_LLM_TIMEOUT_S)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        _llm_fail()
        return None
    if res.returncode != 0:
        _llm_fail()
        return None
    parsed = _extract_json_object(res.stdout)
    if parsed is None:
        _llm_fail()
        return None
    qid = parsed.get("quest_id")
    if not isinstance(qid, str) or qid not in qdef_map:
        _llm_fail()
        return None
    _llm_failures = 0  # success — reset breaker
    return qdef_map[qid], prob_map[qid]


def pick_quest_for_buddy(
    buddy: Buddy, zone_id: str, rng: Optional[random.Random] = None
) -> tuple[QuestDef, float]:
    """Smart selection: try an LLM pick first (Claude chooses the quest the
    buddy feels confident about), then fall back to a dice-weighted pick.
    Returns (quest, probability).
    """
    zone = get_zone(zone_id)
    qdefs = [QUESTS[qid] for qid in zone.quest_ids]

    # Try LLM pick first
    llm_result = _pick_quest_via_llm(buddy, zone_id, qdefs)
    if llm_result is not None:
        return llm_result

    # Fallback: dice-based weighted pick
    r = rng or random
    probs = [_success_probability(buddy, q) for q in qdefs]
    weights = [max(0.05, p) ** 2 for p in probs]
    idx = r.choices(range(len(qdefs)), weights=weights, k=1)[0]
    return qdefs[idx], probs[idx]


def start(
    buddy: Buddy, *, zone_id: str, now: Optional[int] = None,
    rng: Optional[random.Random] = None,
) -> tuple[QuestDef, float]:
    if buddy.quest is not None:
        raise ValueError(f"quest already active: {buddy.quest.id}")
    qdef, prob = pick_quest_for_buddy(buddy, zone_id, rng)
    buddy.quest = Quest(
        id=qdef.id, started_at=now or int(time.time()),
        duration_s=qdef.duration_s,
    )
    buddy.stamina = _clamp_int(buddy.stamina - stamina_cost(buddy, qdef), 0, buddy.max_stamina)
    return qdef, prob


def start_specific(
    buddy: Buddy, quest_id: str, now: Optional[int] = None,
) -> QuestDef:
    """Commit a specific quest without running the smart-picker.

    Used by the activity loop after `pick_for_idle` (or the LLM path)
    selects the exact quest to run. Raises if a quest is already
    active or the id is unknown.
    """
    if buddy.quest is not None:
        raise ValueError(f"quest already active: {buddy.quest.id}")
    qdef = get(quest_id)
    buddy.quest = Quest(
        id=qdef.id, started_at=now or int(time.time()),
        duration_s=qdef.duration_s,
    )
    buddy.stamina = _clamp_int(buddy.stamina - stamina_cost(buddy, qdef), 0, buddy.max_stamina)
    return qdef


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _clamp_int(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, x))


def _trait(buddy: Buddy, key: str) -> int:
    return int(buddy.traits.get(key, 5))


def stamina_cost(buddy: Buddy, qdef: QuestDef) -> int:
    """Stamina deducted when this quest starts. Traits lower the cost."""
    if qdef.category == "rest":
        return 0
    if qdef.category == "gathering":
        return max(3, 10 - _trait(buddy, "patience") // 2)   # 3..10
    return max(10, 25 - _trait(buddy, "boldness"))           # 10..25 combat


def mood_delta_on_claim(buddy: Buddy, qdef: QuestDef, success: bool) -> int:
    """Mood change applied when a quest is claimed. Bold buddies tolerate
    combat better (smaller penalty); gathering and rest are mildly positive.
    """
    if qdef.category == "combat":
        return -max(3, 15 - _trait(buddy, "boldness"))        # -3..-15
    if qdef.category == "gathering":
        return 3 if success else 1
    if qdef.category == "rest":
        return 5 if success else 0
    return 0


def pick_for_idle(buddy: Buddy, rng: random.Random) -> IdleDecision:
    """Deterministic trait-weighted decision for the activity loop.

    Pure function — no state mutation. Used as the fallback when
    `claude -p` is unavailable or returns garbage. Returns a fully
    populated `IdleDecision` that the caller can apply.

    Tiers:
      0. critically tired → force rest or noop
      1. scaled by stamina/mood readiness — act at all?
      2. instant vignette or real task (low mood → tilt to vignette)
      3. gathering vs combat quest (low stamina → demote combat)
    """
    c = _trait(buddy, "curiosity")
    b = _trait(buddy, "boldness")
    p = _trait(buddy, "patience")

    stamina_pct = buddy.stamina / max(1, buddy.max_stamina)
    mood_pct = buddy.mood / max(1, buddy.max_mood)

    # Tier 0 — exhausted → strongly prefer rest
    if stamina_pct < 0.25:
        if "meadow_sun_nap" in QUESTS and rng.random() < 0.7:
            return IdleDecision(
                action="start_quest", quest_id="meadow_sun_nap",
                reason="fallback dice: exhausted → rest",
            )
        return IdleDecision(action="noop", reason="fallback dice: too tired")

    # Tier 1 — act at all? Stamina shapes readiness here; a grumpy but
    # rested buddy still acts (just preferentially into vignettes — see
    # tier 2). Mood doesn't suppress action rate, it only rechannels it
    # toward mood-recovery activities.
    stamina_factor = 0.4 + 0.6 * stamina_pct  # 0.4..1.0
    prob_act = _clamp((0.55 + 0.04 * c + 0.02 * b) * stamina_factor, 0.1, 0.95)
    if rng.random() > prob_act:
        return IdleDecision(action="noop", reason="fallback dice: quiet")

    # Tier 2 — vignette vs real task. Low mood tilts toward vignette (fun
    # activities are what recover mood).
    prob_task_base = 0.15 + 0.05 * c + 0.04 * b - 0.02 * p
    # Scale down further when mood is poor — a grumpy buddy wants
    # comfort, not work.
    mood_factor = 0.5 + 0.5 * mood_pct  # 0.5 at 0 mood, 1.0 at full
    prob_task = _clamp(prob_task_base * mood_factor, 0.05, 0.80)
    if rng.random() > prob_task:
        vignette = vignettes.pick(buddy, rng)
        return IdleDecision(
            action="idle_flavor",
            flavor=vignettes.render(vignette, buddy),
            reason=f"fallback dice: vignette {vignette.id}",
        )

    # Tier 3 — gathering vs combat. Low stamina demotes combat.
    weight_combat = _clamp(0.15 + 0.07 * b, 0.05, 0.85)
    if stamina_pct < 0.4:
        weight_combat *= 0.25  # heavily discourage combat when tired
    category = "combat" if rng.random() < weight_combat else "gathering"
    pool = [
        q for q in QUESTS.values()
        if q.category == category and q.difficulty <= buddy.level + 2
    ]
    if not pool and category == "combat":
        # demote to gathering if combat pool was empty
        category = "gathering"
        pool = [
            q for q in QUESTS.values()
            if q.category == category and q.difficulty <= buddy.level + 2
        ]
    if not pool:
        return IdleDecision(action="noop", reason=f"fallback dice: empty {category} pool")

    if p >= 5:
        weights = [max(1, q.duration_s) for q in pool]
    else:
        weights = [max(1, 300 - q.duration_s) for q in pool]
    chosen = rng.choices(pool, weights=weights, k=1)[0]
    return IdleDecision(
        action="start_quest",
        quest_id=chosen.id,
        reason=f"fallback dice: {category} {chosen.id}",
    )


@dataclass
class QuestResult:
    success: bool
    xp: int
    items: list[str]
    hp_damage: int
    flavor: str
    mana_cost: int = 0
    mana_cast: bool = False
    fired_skills: list[str] = field(default_factory=list)
    probability: float = 0.0
    difficulty: int = 0
    stat_score: float = 0.0
    weakest_stat: Optional[str] = None
    fail_narrative: list[str] = field(default_factory=list)
    combat_log: list[str] = field(default_factory=list)
    defeated_by: Optional[str] = None


def _fire_skills(
    buddy: Buddy,
    trigger: str,
    ctx: dict,
    qdef: Optional["QuestDef"] = None,
    rng: Optional[random.Random] = None,
) -> list[str]:
    """Fire every active skill whose trigger matches, within mana budget.

    Mutates `ctx` in place. Recognized ctx keys:
      - "p" (float): pre-roll success probability
      - "xp" (int): post-roll xp award
      - "dmg" (int): post-roll hp damage
      - "items" (list[str]): post-roll loot

    Returns the list of skill ids that fired (for reporting).
    """
    r = rng or random
    fired: list[str] = []
    for sid in buddy.active_skills:
        try:
            s = skills.get(sid)
        except KeyError:
            continue
        # Only claim-time triggers run through this dispatch; the new
        # live-combat triggers are read directly by combat.py.
        if s.trigger not in ("on_claim", "on_success", "on_failure"):
            continue
        if s.trigger != trigger:
            continue
        if buddy.current_mana < s.mana_cost:
            continue
        if s.effect == "boost_success":
            ctx["p"] = min(0.95, ctx.get("p", 0.0) + s.magnitude / 100)
        elif s.effect == "bonus_xp_pct":
            ctx["xp"] = ctx.get("xp", 0) + ctx.get("xp", 0) * s.magnitude // 100
        elif s.effect == "heal_pct":
            heal = buddy.stats.hp * s.magnitude // 100
            buddy.current_hp = min(buddy.stats.hp, buddy.current_hp + heal)
        elif s.effect == "reduce_damage_pct":
            ctx["dmg"] = ctx.get("dmg", 0) * (100 - s.magnitude) // 100
        elif s.effect == "extra_loot_roll":
            if qdef is not None and qdef.items_on_success:
                for _ in range(s.magnitude):
                    ctx.setdefault("items", []).append(r.choice(list(qdef.items_on_success)))
        elif s.effect == "gathering_extra_item":
            if (
                qdef is not None
                and qdef.category == "gathering"
                and qdef.items_on_success
            ):
                for _ in range(s.magnitude):
                    ctx.setdefault("items", []).append(r.choice(list(qdef.items_on_success)))
        else:
            continue  # unknown effect — ignore
        buddy.current_mana -= s.mana_cost
        fired.append(sid)
    return fired


def claim(buddy: Buddy, rng: Optional[random.Random] = None) -> QuestResult:
    if buddy.quest is None:
        raise ValueError("no active quest")
    if not buddy.quest.is_done():
        raise ValueError(f"quest not finished yet: {buddy.quest.remaining()}s left")
    qdef = get(buddy.quest.id)
    r = rng or random
    p = _success_probability(buddy, qdef)
    # Pre-roll skill pass (boost_success, etc.).
    pre_ctx: dict = {"p": p}
    fired_pre = _fire_skills(buddy, "on_claim", pre_ctx, qdef=qdef, rng=r)
    p = pre_ctx["p"]
    mana_cast = (
        species.get_dominant_stat(buddy.stats) == "int_"
        and buddy.current_mana >= MANA_CAST_COST
    )
    mana_cost = 0
    if mana_cast:
        buddy.current_mana -= MANA_CAST_COST
        mana_cost = MANA_CAST_COST
        p = min(0.95, p + MANA_BOOST)
    score = _stat_score(buddy, qdef)
    weakest = _weakest_key_stat(buddy, qdef)
    success = r.random() < p
    if success:
        xp = r.randint(*qdef.xp_success_range)
        items = list(qdef.items_on_success)
        dmg = 0
        flavor = f"{buddy.name} triumphs at {qdef.name}!"
        narrative: list[str] = []
    else:
        xp = qdef.xp_failure
        items = []
        dmg = int(buddy.stats.hp * qdef.hp_penalty_pct_on_failure / 100)
        flavor = f"{buddy.name} struggled and retreated from {qdef.name}."
        narrative = _build_fail_narrative(buddy, qdef, r)

    # Post-roll skill pass (bonus_xp_pct, heal_pct, reduce_damage_pct, extra_loot_roll).
    post_ctx: dict = {"xp": xp, "items": items, "dmg": dmg}
    fired_post = _fire_skills(
        buddy,
        "on_success" if success else "on_failure",
        post_ctx, qdef=qdef, rng=r,
    )
    xp = post_ctx["xp"]
    items = post_ctx["items"]
    dmg = post_ctx["dmg"]

    buddy.xp += xp
    if items:
        buddy.inventory.extend(items)
    if dmg:
        buddy.current_hp = max(1, buddy.current_hp - dmg)
    # Rest activities full-heal HP, stamina, and mana on success.
    if success and qdef.category == "rest":
        buddy.current_hp = buddy.stats.hp
        buddy.stamina = buddy.max_stamina
        buddy.current_mana = buddy.max_mana
    # Mood delta based on category + outcome.
    buddy.mood = _clamp_int(
        buddy.mood + mood_delta_on_claim(buddy, qdef, success),
        0, buddy.max_mood,
    )
    buddy.quest = None
    return QuestResult(
        success=success, xp=xp, items=items, hp_damage=dmg, flavor=flavor,
        mana_cost=mana_cost, mana_cast=mana_cast,
        fired_skills=fired_pre + fired_post,
        probability=round(p, 3),
        difficulty=qdef.difficulty,
        stat_score=round(score, 2),
        weakest_stat=weakest,
        fail_narrative=narrative,
    )


def fail_from_combat(buddy: Buddy, rng: Optional[random.Random] = None) -> QuestResult:
    """Force-fail the active quest because the buddy lost a combat encounter.

    Mirrors the failure branch of `claim()` but bypasses the timer check, so
    it can be invoked the moment the buddy retreats from a fight. Fires the
    normal on_failure skill pass (iron_skin, second_wind, etc.) and clears
    both `buddy.quest` and any lingering `buddy.combat`.
    """
    if buddy.quest is None:
        raise ValueError("no active quest")
    qdef = get(buddy.quest.id)
    r = rng or random

    # Snapshot the fight transcript before we clear buddy.combat.
    captured_log: list[str] = []
    defeated_by: Optional[str] = None
    if buddy.combat is not None:
        captured_log = list(buddy.combat.log)
        try:
            import combat as combat_mod  # deferred to break the cycle
            defeated_by = combat_mod.get_enemy(buddy.combat.enemy_id).name
        except (KeyError, ImportError):
            pass

    xp = qdef.xp_failure
    dmg = int(buddy.stats.hp * qdef.hp_penalty_pct_on_failure / 100)
    if defeated_by:
        flavor = f"{buddy.name} was overwhelmed by a {defeated_by} during {qdef.name}."
    else:
        flavor = f"{buddy.name} was overwhelmed during {qdef.name}."

    post_ctx: dict = {"xp": xp, "items": [], "dmg": dmg}
    fired = _fire_skills(buddy, "on_failure", post_ctx, qdef=qdef, rng=r)
    xp = post_ctx["xp"]
    dmg = post_ctx["dmg"]

    buddy.xp += xp
    if dmg:
        buddy.current_hp = max(1, buddy.current_hp - dmg)
    buddy.mood = _clamp_int(
        buddy.mood + mood_delta_on_claim(buddy, qdef, success=False),
        0, buddy.max_mood,
    )
    buddy.quest = None
    buddy.combat = None

    p = _success_probability(buddy, qdef)
    return QuestResult(
        success=False, xp=xp, items=[], hp_damage=dmg, flavor=flavor,
        fired_skills=fired,
        probability=round(p, 3),
        difficulty=qdef.difficulty,
        stat_score=round(_stat_score(buddy, qdef), 2),
        weakest_stat=_weakest_key_stat(buddy, qdef),
        combat_log=captured_log,
        defeated_by=defeated_by,
    )


def pick_flavor_line(quest_id: str, buddy_name: str, rng: Optional[random.Random] = None) -> str:
    r = rng or random
    qdef = get(quest_id)
    return f"{buddy_name} {r.choice(qdef.flavor)}"
