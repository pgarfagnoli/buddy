"""Starter species registry with base stats and ASCII sprites."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .state import Stats


TIER_1_LEVEL = 5    # starter tutorial — fast first evolution
TIER_2_LEVEL = 10   # every subsequent evolution fires 10 levels into the new form
TIER_3_LEVEL = 10
TIER_4_LEVEL = 10
TIER_5_LEVEL = 10
TIER_6_LEVEL = 10
TIER_7_LEVEL = 10   # depth-7+ lineages apex-branch here after the split-and-converge rework

# Priority order for breaking ties in get_dominant_stat(). HP is excluded
# because it grows automatically with level and would always dominate.
_DOMINANCE_PRIORITY: tuple[str, ...] = ("atk", "def_", "spd", "luck", "int_", "res")

# Uniform flat stat bonuses applied on each tier-up. Every tier's bonus is
# slightly larger than the last so climbing feels rewarding at higher tiers.
# Most lineages now extend through tier 4 (depth 5); two flagship lines —
# wren (raptors) and guppy (predator fish) — push all the way to tier 6
# (depth 7) before mythic.
_TIER_2_BONUS: dict[str, int] = {
    "hp": 8, "atk": 3, "def_": 3, "spd": 2, "luck": 2, "int_": 1, "res": 1,
}
_TIER_3_BONUS: dict[str, int] = {
    "hp": 10, "atk": 4, "def_": 4, "spd": 3, "luck": 2, "int_": 1, "res": 1,
}
_TIER_4_BONUS: dict[str, int] = {
    "hp": 12, "atk": 5, "def_": 5, "spd": 3, "luck": 3, "int_": 2, "res": 2,
}
_TIER_5_BONUS: dict[str, int] = {
    "hp": 14, "atk": 6, "def_": 5, "spd": 4, "luck": 3, "int_": 2, "res": 2,
}
_TIER_6_BONUS: dict[str, int] = {
    "hp": 16, "atk": 7, "def_": 6, "spd": 5, "luck": 3, "int_": 2, "res": 2,
}
_TIER_7_BONUS: dict[str, int] = {
    "hp": 18, "atk": 8, "def_": 7, "spd": 5, "luck": 4, "int_": 3, "res": 3,
}


@dataclass(frozen=True)
class Evolution:
    """One branch of a species evolution. `requirements` is a dict of
    {stat_key: minimum_value} the buddy must meet to be eligible for this
    branch — every entry must be satisfied (logical AND). `stat_bonus` is
    the flat delta applied to the buddy's current Stats on evolve.
    """
    evolved_species_id: str
    requirements: dict[str, int] = field(default_factory=dict)
    stat_bonus: dict[str, int] = field(default_factory=dict)
    grants_skill: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.requirements:
            raise ValueError(
                f"Evolution to {self.evolved_species_id!r} must declare "
                f"at least one stat requirement"
            )


@dataclass(frozen=True)
class Species:
    id: str
    display_name: str
    kind: str  # beast / insect / aquatic / amphibian / reptile / avian (fire/water/normal reserved)
    base_hp: int
    base_atk: int
    base_def: int
    base_spd: int
    base_luck: int
    blurb: str
    evolutions: tuple[Evolution, ...] = ()
    sprite_fallback: Optional[str] = None
    is_starter: bool = True
    evolves_at: Optional[int] = None  # level at which `evolutions` fires; None = terminal
    mythic_at: Optional[int] = None   # level at which an apex may invoke a mythic evolution
    # Additive personality nudges applied on top of the random roll in
    # choose_buddy. Keys: curiosity, boldness, patience. Values in [-3, +3].
    # Empty → no bias.
    trait_bias: dict[str, int] = field(default_factory=dict)
    inherent_skills: tuple[str, ...] = ()


SPECIES: dict[str, Species] = {
    # ─── starters (Lv 1-4) ──────────────────────────────────────────────────
    "rabbit": Species(
        id="rabbit", display_name="Rabbit", kind="beast",
        base_hp=11, base_atk=5, base_def=5, base_spd=9, base_luck=6,
        blurb="A twitchy sprinter. Dodges first, thinks later.",
        evolutions=(
            Evolution("hare", requirements={"spd": 12, "atk": 12}, stat_bonus={"hp": 3, "atk": 2, "spd": 4, "luck": 1}),
            Evolution("lop_rabbit", requirements={"def_": 12, "luck": 12}, stat_bonus={"hp": 5, "def_": 3, "luck": 2}),
        ),
        evolves_at=TIER_1_LEVEL,
        trait_bias={"curiosity": 2, "patience": -2},
        inherent_skills=("scout",),
    ),
    "field_mouse": Species(
        id="field_mouse", display_name="Field Mouse", kind="beast",
        base_hp=9, base_atk=5, base_def=4, base_spd=8, base_luck=9,
        blurb="A lucky little scout. Finds crumbs everyone else misses.",
        evolutions=(
            Evolution("brown_rat", requirements={"atk": 12, "int_": 12}, stat_bonus={"hp": 3, "atk": 3, "def_": 2, "int_": 2}),
            Evolution("dormouse", requirements={"luck": 12, "res": 12}, stat_bonus={"hp": 4, "def_": 3, "luck": 3}),
        ),
        evolves_at=TIER_1_LEVEL,
        trait_bias={"curiosity": 3, "boldness": -1},
    ),
    "squirrel": Species(
        id="squirrel", display_name="Squirrel", kind="beast",
        base_hp=10, base_atk=6, base_def=5, base_spd=8, base_luck=6,
        blurb="A balanced acrobat. Great in the canopy.",
        evolutions=(
            Evolution("red_squirrel", requirements={"atk": 12, "spd": 12}, stat_bonus={"hp": 3, "atk": 3, "spd": 3, "luck": 1}),
            Evolution("chipmunk", requirements={"luck": 12, "int_": 12}, stat_bonus={"hp": 3, "def_": 2, "luck": 4, "int_": 1}),
        ),
        evolves_at=TIER_1_LEVEL,
        trait_bias={"curiosity": 2, "boldness": 1},
    ),
    "ant": Species(
        id="ant", display_name="Ant", kind="insect",
        base_hp=8, base_atk=7, base_def=8, base_spd=6, base_luck=6,
        blurb="A tiny tank. Carries ten times its weight.",
        evolutions=(
            Evolution("soldier_ant", requirements={"atk": 12}, stat_bonus={"hp": 3, "atk": 4, "def_": 3}),
            Evolution("carpenter_ant", requirements={"def_": 12, "res": 12}, stat_bonus={"hp": 5, "def_": 4, "res": 1}),
        ),
        evolves_at=TIER_1_LEVEL,
        trait_bias={"patience": 3, "curiosity": -1},
    ),
    "bee": Species(
        id="bee", display_name="Bee", kind="insect",
        base_hp=7, base_atk=10, base_def=3, base_spd=9, base_luck=5,
        blurb="A glass-cannon stinger. Hits hard, folds fast.",
        evolutions=(
            Evolution("wasp", requirements={"atk": 12, "spd": 12}, stat_bonus={"hp": 2, "atk": 4, "spd": 4}),
            Evolution("bumblebee", requirements={"def_": 12, "hp": 12}, stat_bonus={"hp": 5, "def_": 3, "luck": 2}),
        ),
        evolves_at=TIER_1_LEVEL,
        trait_bias={"boldness": 3, "curiosity": 2, "patience": -2},
    ),
    "ladybug": Species(
        id="ladybug", display_name="Ladybug", kind="insect",
        base_hp=9, base_atk=5, base_def=7, base_spd=5, base_luck=9,
        blurb="A lucky defender. Spotted shell, spotted fortune.",
        evolutions=(
            Evolution("firefly", requirements={"luck": 12, "int_": 12}, stat_bonus={"hp": 2, "atk": 2, "luck": 4, "int_": 2}),
            Evolution("stag_beetle", requirements={"atk": 12, "def_": 12}, stat_bonus={"hp": 4, "atk": 3, "def_": 3}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),
    "caterpillar": Species(
        id="caterpillar", display_name="Caterpillar", kind="insect",
        base_hp=14, base_atk=4, base_def=9, base_spd=2, base_luck=6,
        blurb="A slow bulwark. Eats leaves, absorbs hits.",
        evolutions=(
            Evolution("butterfly", requirements={"spd": 12, "int_": 12}, stat_bonus={"hp": 1, "spd": 4, "int_": 4, "luck": 1}),
            Evolution("moth", requirements={"res": 12, "luck": 12}, stat_bonus={"hp": 3, "def_": 1, "luck": 3, "res": 3}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),
    "tadpole": Species(
        id="tadpole", display_name="Tadpole", kind="amphibian",
        base_hp=10, base_atk=5, base_def=6, base_spd=7, base_luck=7,
        blurb="An adaptable amphibian. Grows into something bigger.",
        evolutions=(
            Evolution("frog", requirements={"atk": 12, "spd": 12}, stat_bonus={"hp": 3, "atk": 3, "def_": 1, "spd": 3}),
            Evolution("toad", requirements={"def_": 12}, stat_bonus={"hp": 5, "def_": 3, "luck": 2}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),
    "minnow": Species(
        id="minnow", display_name="Minnow", kind="aquatic",
        base_hp=8, base_atk=6, base_def=4, base_spd=10, base_luck=7,
        blurb="A slippery evader. Blink and you'll miss it.",
        evolutions=(
            Evolution("trout", requirements={"spd": 12, "atk": 12}, stat_bonus={"hp": 3, "atk": 3, "spd": 4}),
            Evolution("carp", requirements={"def_": 12, "luck": 12}, stat_bonus={"hp": 5, "def_": 3, "luck": 2}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),
    "snail": Species(
        id="snail", display_name="Snail", kind="aquatic",
        base_hp=13, base_atk=3, base_def=12, base_spd=1, base_luck=6,
        blurb="A shell fortress. Arrives eventually, survives always.",
        evolutions=(
            Evolution("conch", requirements={"res": 12, "int_": 12}, stat_bonus={"hp": 3, "def_": 2, "int_": 2, "res": 3}),
            Evolution("giant_snail", requirements={"def_": 12}, stat_bonus={"hp": 6, "def_": 4}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),
    "sparrow": Species(
        id="sparrow", display_name="Sparrow", kind="avian",
        base_hp=9, base_atk=6, base_def=4, base_spd=9, base_luck=7,
        blurb="A swift striker. Quick beak, quicker wings.",
        evolutions=(
            Evolution("swallow", requirements={"spd": 12, "luck": 12}, stat_bonus={"hp": 2, "atk": 2, "spd": 4, "luck": 2}),
            Evolution("crow", requirements={"atk": 12, "int_": 12}, stat_bonus={"hp": 3, "atk": 4, "int_": 3}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),
    "chick": Species(
        id="chick", display_name="Chick", kind="avian",
        base_hp=11, base_atk=6, base_def=6, base_spd=6, base_luck=6,
        blurb="An all-rounder rookie. Fluff now, fury later.",
        evolutions=(
            Evolution("rooster", requirements={"atk": 12, "spd": 12}, stat_bonus={"hp": 3, "atk": 4, "spd": 3}),
            Evolution("hen", requirements={"def_": 12}, stat_bonus={"hp": 5, "def_": 3, "luck": 2}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),
    "hedgehog": Species(
        id="hedgehog", display_name="Hedgehog", kind="beast",
        base_hp=11, base_atk=4, base_def=10, base_spd=4, base_luck=6,
        blurb="A prickly recluse. Curl up and outlast.",
        evolutions=(
            Evolution("porcupine", requirements={"atk": 12}, stat_bonus={"hp": 4, "atk": 3, "def_": 3}),
            Evolution("echidna", requirements={"def_": 12, "int_": 12}, stat_bonus={"hp": 5, "def_": 3, "int_": 2}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),
    "guppy": Species(
        id="guppy", display_name="Guppy", kind="aquatic",
        base_hp=7, base_atk=5, base_def=4, base_spd=11, base_luck=9,
        blurb="A rainbow streak. Quick, lucky, gone.",
        evolutions=(
            Evolution("goldfish", requirements={"spd": 12, "luck": 12}, stat_bonus={"hp": 3, "spd": 4, "luck": 3}),
            Evolution("bass", requirements={"atk": 12, "def_": 12}, stat_bonus={"hp": 4, "atk": 4, "def_": 2}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),
    "shrimp": Species(
        id="shrimp", display_name="Shrimp", kind="aquatic",
        base_hp=8, base_atk=6, base_def=7, base_spd=9, base_luck=6,
        blurb="Tiny but armored. Snaps first, apologizes never.",
        evolutions=(
            Evolution("prawn", requirements={"spd": 12, "int_": 12}, stat_bonus={"hp": 2, "atk": 2, "spd": 4, "int_": 2}),
            Evolution("crayfish", requirements={"atk": 12, "def_": 12}, stat_bonus={"hp": 4, "atk": 4, "def_": 2}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),
    "froglet": Species(
        id="froglet", display_name="Froglet", kind="amphibian",
        base_hp=10, base_atk=6, base_def=5, base_spd=8, base_luck=7,
        blurb="A leaper in training. Sticky tongue, stickier plans.",
        evolutions=(
            Evolution("tree_frog", requirements={"spd": 12, "luck": 12}, stat_bonus={"hp": 3, "spd": 4, "luck": 3}),
            Evolution("bullfrog", requirements={"atk": 12}, stat_bonus={"hp": 5, "atk": 4, "def_": 1}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),
    "newt": Species(
        id="newt", display_name="Newt", kind="amphibian",
        base_hp=12, base_atk=4, base_def=7, base_spd=6, base_luck=8,
        blurb="A slow regrower. Lose a tail, grow another.",
        evolutions=(
            Evolution("salamander", requirements={"res": 12, "int_": 12}, stat_bonus={"hp": 3, "def_": 2, "int_": 2, "res": 3}),
            Evolution("fire_newt", requirements={"atk": 12}, stat_bonus={"hp": 4, "atk": 3, "res": 3}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),
    "axolotl": Species(
        id="axolotl", display_name="Axolotl", kind="amphibian",
        base_hp=11, base_atk=5, base_def=6, base_spd=6, base_luck=9,
        blurb="A smile you can't unsee. Regenerates through sheer vibes.",
        evolutions=(
            Evolution("tiger_salamander", requirements={"atk": 12}, stat_bonus={"hp": 4, "atk": 3, "def_": 3}),
            Evolution("giant_salamander", requirements={"def_": 12, "hp": 12}, stat_bonus={"hp": 6, "def_": 4}),
        ),
        evolves_at=TIER_1_LEVEL,
        inherent_skills=("focus",),
    ),
    "baby_gecko": Species(
        id="baby_gecko", display_name="Baby Gecko", kind="reptile",
        base_hp=8, base_atk=6, base_def=5, base_spd=10, base_luck=8,
        blurb="A wall-walker. Sticks and runs.",
        evolutions=(
            Evolution("tokay_gecko", requirements={"atk": 12, "def_": 12}, stat_bonus={"hp": 3, "atk": 4, "def_": 3}),
            Evolution("house_gecko", requirements={"spd": 12, "luck": 12}, stat_bonus={"hp": 3, "spd": 4, "luck": 3}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),
    "hatchling_turtle": Species(
        id="hatchling_turtle", display_name="Hatchling Turtle", kind="reptile",
        base_hp=13, base_atk=4, base_def=11, base_spd=3, base_luck=6,
        blurb="A shelled wanderer. Slow today, slow tomorrow.",
        evolutions=(
            Evolution("snapping_turtle", requirements={"atk": 12}, stat_bonus={"hp": 4, "atk": 4, "def_": 2}),
            Evolution("box_turtle", requirements={"def_": 12, "hp": 12}, stat_bonus={"hp": 6, "def_": 4}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),
    "anole": Species(
        id="anole", display_name="Anole", kind="reptile",
        base_hp=9, base_atk=7, base_def=5, base_spd=9, base_luck=7,
        blurb="A green ambush specialist. Flash the throat, strike twice.",
        evolutions=(
            Evolution("iguana", requirements={"def_": 12}, stat_bonus={"hp": 5, "atk": 1, "def_": 4}),
            Evolution("basilisk", requirements={"spd": 12, "atk": 12}, stat_bonus={"hp": 3, "atk": 3, "spd": 4}),
        ),
        evolves_at=TIER_1_LEVEL,
        inherent_skills=("ambush",),
    ),
    "skink": Species(
        id="skink", display_name="Skink", kind="reptile",
        base_hp=10, base_atk=6, base_def=6, base_spd=8, base_luck=7,
        blurb="A striped bolt. Drops its tail on command.",
        evolutions=(
            Evolution("monitor_lizard", requirements={"atk": 12}, stat_bonus={"hp": 4, "atk": 4, "def_": 2}),
            Evolution("blue_tongue_skink", requirements={"def_": 12, "int_": 12}, stat_bonus={"hp": 5, "def_": 3, "int_": 2}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),
    "wren": Species(
        id="wren", display_name="Wren", kind="avian",
        base_hp=8, base_atk=6, base_def=4, base_spd=10, base_luck=8,
        blurb="A pocket-sized shout. Punches above its weight.",
        evolutions=(
            Evolution("kestrel", requirements={"atk": 12, "spd": 12}, stat_bonus={"hp": 3, "atk": 3, "spd": 4}),
            Evolution("nightingale", requirements={"int_": 12, "luck": 12}, stat_bonus={"hp": 2, "luck": 3, "int_": 4}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),
    "duckling": Species(
        id="duckling", display_name="Duckling", kind="avian",
        base_hp=11, base_atk=5, base_def=6, base_spd=7, base_luck=8,
        blurb="A fluff with feet. Follows the first thing it sees.",
        evolutions=(
            Evolution("mallard", requirements={"spd": 12, "luck": 12}, stat_bonus={"hp": 3, "spd": 4, "luck": 3}),
            Evolution("swan", requirements={"def_": 12, "atk": 12}, stat_bonus={"hp": 4, "atk": 3, "def_": 3}),
        ),
        evolves_at=TIER_1_LEVEL,
    ),

    # ─── evolved forms (Lv 5+, not selectable as starters) ─────────────────
    # beasts
    "hare": Species(
        id="hare", display_name="Hare", kind="beast",
        base_hp=14, base_atk=7, base_def=5, base_spd=13, base_luck=7,
        blurb="A long-legged sprinter. Clears a meadow in a heartbeat.",
        evolutions=(Evolution("jackrabbit", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="rabbit", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "lop_rabbit": Species(
        id="lop_rabbit", display_name="Lop Rabbit", kind="beast",
        base_hp=16, base_atk=5, base_def=8, base_spd=9, base_luck=8,
        blurb="A stout survivor. Long ears, long patience.",
        evolutions=(Evolution("jackrabbit", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="rabbit", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "brown_rat": Species(
        id="brown_rat", display_name="Brown Rat", kind="beast",
        base_hp=12, base_atk=8, base_def=6, base_spd=8, base_luck=9,
        blurb="A cunning scavenger. Thinks its way through trouble.",
        evolutions=(Evolution("capybara", requirements={"luck": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="field_mouse", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "dormouse": Species(
        id="dormouse", display_name="Dormouse", kind="beast",
        base_hp=13, base_atk=5, base_def=7, base_spd=8, base_luck=12,
        blurb="A tree-dwelling napper. Lucky and cozy.",
        evolutions=(Evolution("capybara", requirements={"luck": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="field_mouse", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "red_squirrel": Species(
        id="red_squirrel", display_name="Red Squirrel", kind="beast",
        base_hp=13, base_atk=9, base_def=5, base_spd=11, base_luck=7,
        blurb="A high-canopy brawler. Territorial and quick.",
        evolutions=(Evolution("marmot", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="squirrel", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "chipmunk": Species(
        id="chipmunk", display_name="Chipmunk", kind="beast",
        base_hp=13, base_atk=6, base_def=7, base_spd=8, base_luck=10,
        blurb="A cheek-stuffing strategist. Hoards its luck.",
        evolutions=(Evolution("marmot", requirements={"luck": 16}, stat_bonus=_TIER_2_BONUS),),
        inherent_skills=("treasure_sense",),
        sprite_fallback="squirrel", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "porcupine": Species(
        id="porcupine", display_name="Porcupine", kind="beast",
        base_hp=15, base_atk=7, base_def=13, base_spd=4, base_luck=6,
        blurb="A rolling pincushion. Touch at your peril.",
        evolutions=(Evolution("pangolin", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS, grants_skill="hearty"),),
        sprite_fallback="hedgehog", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "echidna": Species(
        id="echidna", display_name="Echidna", kind="beast",
        base_hp=16, base_atk=4, base_def=13, base_spd=4, base_luck=6,
        blurb="An old-world oddity. Patient and prickly.",
        evolutions=(Evolution("pangolin", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="hedgehog", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),

    # insects
    "soldier_ant": Species(
        id="soldier_ant", display_name="Soldier Ant", kind="insect",
        base_hp=11, base_atk=11, base_def=11, base_spd=6, base_luck=6,
        blurb="A mandibled bruiser. Marches in a square.",
        evolutions=(Evolution("army_ant", requirements={"atk": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="ant", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "carpenter_ant": Species(
        id="carpenter_ant", display_name="Carpenter Ant", kind="insect",
        base_hp=13, base_atk=7, base_def=12, base_spd=6, base_luck=6,
        blurb="A wood-chewing tank. Builds and endures.",
        evolutions=(Evolution("army_ant", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="ant", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "wasp": Species(
        id="wasp", display_name="Wasp", kind="insect",
        base_hp=9, base_atk=14, base_def=3, base_spd=13, base_luck=5,
        blurb="A paper-nest menace. Faster and meaner than it looks.",
        evolutions=(Evolution("giant_hornet", requirements={"atk": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="bee", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "bumblebee": Species(
        id="bumblebee", display_name="Bumblebee", kind="insect",
        base_hp=12, base_atk=10, base_def=6, base_spd=9, base_luck=7,
        blurb="A fuzzy tank. Shouldn't fly, does anyway.",
        evolutions=(Evolution("giant_hornet", requirements={"atk": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="bee", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "firefly": Species(
        id="firefly", display_name="Firefly", kind="insect",
        base_hp=11, base_atk=7, base_def=7, base_spd=5, base_luck=13,
        blurb="A flicker of luck. Brightest at dusk.",
        evolutions=(Evolution("rhinoceros_beetle", requirements={"luck": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="ladybug", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "stag_beetle": Species(
        id="stag_beetle", display_name="Stag Beetle", kind="insect",
        base_hp=13, base_atk=8, base_def=10, base_spd=5, base_luck=9,
        blurb="A chitinous duelist. Those mandibles aren't decorative.",
        evolutions=(Evolution("rhinoceros_beetle", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="ladybug", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "butterfly": Species(
        id="butterfly", display_name="Butterfly", kind="insect",
        base_hp=15, base_atk=4, base_def=9, base_spd=6, base_luck=7,
        blurb="A drifting wonder. Deceptively agile on the wing.",
        evolutions=(Evolution("atlas_moth", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="caterpillar", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "moth": Species(
        id="moth", display_name="Moth", kind="insect",
        base_hp=17, base_atk=4, base_def=10, base_spd=2, base_luck=9,
        blurb="A night-drifter. Dust on its wings is not for you.",
        evolutions=(Evolution("atlas_moth", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="caterpillar", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),

    # amphibians
    "frog": Species(
        id="frog", display_name="Frog", kind="amphibian",
        base_hp=13, base_atk=8, base_def=7, base_spd=10, base_luck=7,
        blurb="A full-grown hopper. Tongue like a whip.",
        evolutions=(Evolution("goliath_frog", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="tadpole", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "toad": Species(
        id="toad", display_name="Toad", kind="amphibian",
        base_hp=15, base_atk=5, base_def=9, base_spd=7, base_luck=9,
        blurb="A warty sitter. Knows every root in the forest.",
        evolutions=(Evolution("goliath_frog", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="tadpole", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "tree_frog": Species(
        id="tree_frog", display_name="Tree Frog", kind="amphibian",
        base_hp=13, base_atk=6, base_def=5, base_spd=12, base_luck=10,
        blurb="A vivid climber. Sticky pads, sharp eye.",
        evolutions=(Evolution("cane_toad", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="froglet", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "bullfrog": Species(
        id="bullfrog", display_name="Bullfrog", kind="amphibian",
        base_hp=15, base_atk=10, base_def=6, base_spd=8, base_luck=7,
        blurb="A booming bruiser. Weighs more than it looks.",
        evolutions=(Evolution("cane_toad", requirements={"atk": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="froglet", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "salamander": Species(
        id="salamander", display_name="Salamander", kind="amphibian",
        base_hp=15, base_atk=4, base_def=9, base_spd=6, base_luck=8,
        blurb="A glossy regenerator. Shrugs off insults.",
        evolutions=(Evolution("hellbender", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="newt", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "fire_newt": Species(
        id="fire_newt", display_name="Fire Newt", kind="amphibian",
        base_hp=16, base_atk=7, base_def=7, base_spd=6, base_luck=8,
        blurb="A warm-blooded oddity. Toxic skin, short fuse.",
        evolutions=(Evolution("hellbender", requirements={"luck": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="newt", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "tiger_salamander": Species(
        id="tiger_salamander", display_name="Tiger Salamander", kind="amphibian",
        base_hp=15, base_atk=8, base_def=9, base_spd=6, base_luck=9,
        blurb="A patterned ambusher. Slow until it isn't.",
        evolutions=(Evolution("olm", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="axolotl", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "giant_salamander": Species(
        id="giant_salamander", display_name="Giant Salamander", kind="amphibian",
        base_hp=17, base_atk=5, base_def=10, base_spd=6, base_luck=9,
        blurb="A river-bed boulder. Still waters, huge teeth.",
        evolutions=(Evolution("olm", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="axolotl", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),

    # aquatic
    "trout": Species(
        id="trout", display_name="Trout", kind="aquatic",
        base_hp=11, base_atk=9, base_def=4, base_spd=14, base_luck=7,
        blurb="A rivers-end sprinter. Leaps upstream for fun.",
        evolutions=(Evolution("sturgeon", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="minnow", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "carp": Species(
        id="carp", display_name="Carp", kind="aquatic",
        base_hp=13, base_atk=6, base_def=7, base_spd=10, base_luck=9,
        blurb="A long-lived patient drifter. Big scales, bigger calm.",
        evolutions=(Evolution("sturgeon", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="minnow", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "conch": Species(
        id="conch", display_name="Conch", kind="aquatic",
        base_hp=16, base_atk=3, base_def=14, base_spd=1, base_luck=6,
        blurb="A hollow-voiced oracle. The sea remembers through it.",
        evolutions=(Evolution("giant_clam", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="snail", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "giant_snail": Species(
        id="giant_snail", display_name="Giant Snail", kind="aquatic",
        base_hp=19, base_atk=3, base_def=16, base_spd=1, base_luck=6,
        blurb="A moving castle. Nothing gets through that shell.",
        evolutions=(Evolution("giant_clam", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="snail", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "goldfish": Species(
        id="goldfish", display_name="Goldfish", kind="aquatic",
        base_hp=10, base_atk=5, base_def=4, base_spd=15, base_luck=12,
        blurb="A pond-shimmer with three-second memory and endless luck.",
        evolutions=(Evolution("pike", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="guppy", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "bass": Species(
        id="bass", display_name="Bass", kind="aquatic",
        base_hp=11, base_atk=9, base_def=6, base_spd=11, base_luck=9,
        blurb="A muscle with fins. Eats what it wants.",
        evolutions=(Evolution("pike", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="guppy", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "prawn": Species(
        id="prawn", display_name="Prawn", kind="aquatic",
        base_hp=10, base_atk=8, base_def=7, base_spd=13, base_luck=6,
        blurb="A shell-clacking scout. Quicker in the reeds than on the plate.",
        evolutions=(Evolution("lobster", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="shrimp", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "crayfish": Species(
        id="crayfish", display_name="Crayfish", kind="aquatic",
        base_hp=12, base_atk=10, base_def=9, base_spd=9, base_luck=6,
        blurb="A freshwater brawler. Claws first.",
        evolutions=(Evolution("lobster", requirements={"atk": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="shrimp", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),

    # avian
    "swallow": Species(
        id="swallow", display_name="Swallow", kind="avian",
        base_hp=11, base_atk=8, base_def=4, base_spd=13, base_luck=9,
        blurb="A summer-blur arc. Catches flies mid-sentence.",
        evolutions=(Evolution("raven", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="sparrow", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "crow": Species(
        id="crow", display_name="Crow", kind="avian",
        base_hp=12, base_atk=10, base_def=4, base_spd=9, base_luck=7,
        blurb="A clever black-feathered thinker. Holds grudges.",
        evolutions=(Evolution("raven", requirements={"atk": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="sparrow", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "rooster": Species(
        id="rooster", display_name="Rooster", kind="avian",
        base_hp=14, base_atk=10, base_def=6, base_spd=9, base_luck=6,
        blurb="A crowing battler. Spurs and swagger.",
        evolutions=(Evolution("peacock", requirements={"atk": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="chick", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "hen": Species(
        id="hen", display_name="Hen", kind="avian",
        base_hp=16, base_atk=6, base_def=9, base_spd=6, base_luck=8,
        blurb="A matronly tank. Don't come near the chicks.",
        evolutions=(Evolution("peacock", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="chick", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "kestrel": Species(
        id="kestrel", display_name="Kestrel", kind="avian",
        base_hp=11, base_atk=9, base_def=4, base_spd=14, base_luck=8,
        blurb="A hovering hunter. Stoops from the sky.",
        evolutions=(Evolution("peregrine_falcon", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="wren", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "nightingale": Species(
        id="nightingale", display_name="Nightingale", kind="avian",
        base_hp=10, base_atk=6, base_def=4, base_spd=10, base_luck=11,
        blurb="A twilight songstress. Clever to her feathers.",
        evolutions=(Evolution("peregrine_falcon", requirements={"luck": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="wren", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "mallard": Species(
        id="mallard", display_name="Mallard", kind="avian",
        base_hp=14, base_atk=5, base_def=6, base_spd=11, base_luck=11,
        blurb="A glinting-greenhead river drifter.",
        evolutions=(Evolution("pelican", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="duckling", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "swan": Species(
        id="swan", display_name="Swan", kind="avian",
        base_hp=15, base_atk=8, base_def=9, base_spd=7, base_luck=8,
        blurb="A regal, territorial beauty. Broken-wing bluff, real-wing wallop.",
        evolutions=(Evolution("pelican", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="duckling", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),

    # reptile
    "tokay_gecko": Species(
        id="tokay_gecko", display_name="Tokay Gecko", kind="reptile",
        base_hp=11, base_atk=10, base_def=8, base_spd=10, base_luck=8,
        blurb="A loudmouth wall-climber. Bites and holds.",
        evolutions=(Evolution("leopard_gecko", requirements={"atk": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="baby_gecko", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "house_gecko": Species(
        id="house_gecko", display_name="House Gecko", kind="reptile",
        base_hp=11, base_atk=6, base_def=5, base_spd=14, base_luck=11,
        blurb="An indoor acrobat. Fast, calm, unbothered.",
        evolutions=(Evolution("leopard_gecko", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="baby_gecko", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "snapping_turtle": Species(
        id="snapping_turtle", display_name="Snapping Turtle", kind="reptile",
        base_hp=17, base_atk=8, base_def=13, base_spd=3, base_luck=6,
        blurb="A hinge-jawed ambusher. Do not offer a finger.",
        evolutions=(Evolution("alligator_snapping_turtle", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="hatchling_turtle", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "box_turtle": Species(
        id="box_turtle", display_name="Box Turtle", kind="reptile",
        base_hp=19, base_atk=4, base_def=15, base_spd=3, base_luck=6,
        blurb="A vault on legs. Closes up and waits you out.",
        evolutions=(Evolution("alligator_snapping_turtle", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="hatchling_turtle", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "iguana": Species(
        id="iguana", display_name="Iguana", kind="reptile",
        base_hp=14, base_atk=8, base_def=9, base_spd=9, base_luck=7,
        blurb="A sun-basking drama queen. Tail-whips if annoyed.",
        evolutions=(Evolution("chameleon", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="anole", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "basilisk": Species(
        id="basilisk", display_name="Basilisk", kind="reptile",
        base_hp=12, base_atk=10, base_def=5, base_spd=13, base_luck=7,
        blurb="A water-running show-off. Runs across a pond on a dare.",
        evolutions=(Evolution("chameleon", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="anole", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "monitor_lizard": Species(
        id="monitor_lizard", display_name="Monitor Lizard", kind="reptile",
        base_hp=14, base_atk=10, base_def=8, base_spd=8, base_luck=7,
        blurb="A walking cold-blooded hunter. Sizes you up for dinner.",
        evolutions=(Evolution("komodo_dragon", requirements={"atk": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="skink", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),
    "blue_tongue_skink": Species(
        id="blue_tongue_skink", display_name="Blue-Tongue Skink", kind="reptile",
        base_hp=15, base_atk=6, base_def=9, base_spd=8, base_luck=7,
        blurb="A startled shrieker. That tongue is a weapon of surprise.",
        evolutions=(Evolution("komodo_dragon", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),),
        sprite_fallback="skink", is_starter=False, evolves_at=TIER_2_LEVEL,
    ),

    # ─── tier-2 convergent forms (Lv 15+, terminal) ────────────────────────
    # beasts
    "jackrabbit": Species(
        id="jackrabbit", display_name="Jackrabbit", kind="beast",
        base_hp=20, base_atk=9, base_def=8, base_spd=15, base_luck=10,
        blurb="A desert-long runner. Outruns everything that wants it dead.",
        evolutions=(
            Evolution("arctic_hare", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("marsh_pika", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="rabbit", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "capybara": Species(
        id="capybara", display_name="Capybara", kind="beast",
        base_hp=22, base_atk=8, base_def=10, base_spd=8, base_luck=12,
        blurb="The world's largest rodent. Unflappable river-lounger.",
        evolutions=(
            Evolution("beaver", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("shrew_hunter", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="field_mouse", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "marmot": Species(
        id="marmot", display_name="Marmot", kind="beast",
        base_hp=20, base_atk=10, base_def=10, base_spd=10, base_luck=10,
        blurb="A mountain whistler. Stout, watchful, surprisingly fast.",
        evolutions=(
            Evolution("prairie_dog", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("red_fox_kit", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="squirrel", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "pangolin": Species(
        id="pangolin", display_name="Pangolin", kind="beast",
        base_hp=22, base_atk=8, base_def=17, base_spd=6, base_luck=8,
        blurb="A scaled ant-eater. Walking armor plate by plate.",
        evolutions=(
            Evolution("armadillo", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("mountain_mole", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="hedgehog", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),

    # insects
    "army_ant": Species(
        id="army_ant", display_name="Army Ant", kind="insect",
        base_hp=18, base_atk=14, base_def=14, base_spd=9, base_luck=7,
        blurb="A column that eats a forest. Nothing stands in its path.",
        evolutions=(
            Evolution("bullet_ant", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("scarab_beetle", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="ant", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "giant_hornet": Species(
        id="giant_hornet", display_name="Giant Hornet", kind="insect",
        base_hp=15, base_atk=18, base_def=7, base_spd=16, base_luck=7,
        blurb="A murder in airborne form. A single sting is an event.",
        evolutions=(
            Evolution("velvet_ant", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("moth_wasp", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="bee", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "rhinoceros_beetle": Species(
        id="rhinoceros_beetle", display_name="Rhinoceros Beetle", kind="insect",
        base_hp=19, base_atk=13, base_def=13, base_spd=7, base_luck=11,
        blurb="A horn-charging giant. Can lift 850 times its weight.",
        evolutions=(
            Evolution("hercules_beetle", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("glow_bug", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="ladybug", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "atlas_moth": Species(
        id="atlas_moth", display_name="Atlas Moth", kind="insect",
        base_hp=22, base_atk=7, base_def=13, base_spd=8, base_luck=10,
        blurb="A wing-map as wide as your hand. Old as any forest.",
        evolutions=(
            Evolution("hercules_moth", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("stick_bug", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="caterpillar", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),

    # amphibians
    "goliath_frog": Species(
        id="goliath_frog", display_name="Goliath Frog", kind="amphibian",
        base_hp=21, base_atk=13, base_def=12, base_spd=12, base_luck=9,
        blurb="The biggest frog on earth. Leaps ten feet on a whim.",
        evolutions=(
            Evolution("beelzebufo", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("axolot_serpent", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="tadpole", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "cane_toad": Species(
        id="cane_toad", display_name="Cane Toad", kind="amphibian",
        base_hp=20, base_atk=13, base_def=12, base_spd=10, base_luck=9,
        blurb="An unstoppable invader. Toxic, prolific, relentless.",
        evolutions=(
            Evolution("poison_dart_frog", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("clawed_frog", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="froglet", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "hellbender": Species(
        id="hellbender", display_name="Hellbender", kind="amphibian",
        base_hp=23, base_atk=10, base_def=14, base_spd=8, base_luck=10,
        blurb="A two-foot river salamander. Hunts by feel in the dark.",
        evolutions=(
            Evolution("mudpuppy", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("cave_salamander", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="newt", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "olm": Species(
        id="olm", display_name="Olm", kind="amphibian",
        base_hp=23, base_atk=11, base_def=14, base_spd=8, base_luck=11,
        blurb="A blind cave-dweller. Lives a century without seeing the sun.",
        evolutions=(
            Evolution("waterdog", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("pond_wyrm", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="axolotl", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),

    # aquatic
    "sturgeon": Species(
        id="sturgeon", display_name="Sturgeon", kind="aquatic",
        base_hp=20, base_atk=13, base_def=11, base_spd=15, base_luck=9,
        blurb="A living fossil. Older than dinosaurs, meaner than it looks.",
        evolutions=(
            Evolution("arapaima", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("reef_shark", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="minnow", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "giant_clam": Species(
        id="giant_clam", display_name="Giant Clam", kind="aquatic",
        base_hp=25, base_atk=6, base_def=20, base_spd=1, base_luck=8,
        blurb="A reef cornerstone. Quiet for a century, shuts in a blink.",
        evolutions=(
            Evolution("triton_shell", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("hermit_crab", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="snail", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "pike": Species(
        id="pike", display_name="Pike", kind="aquatic",
        base_hp=17, base_atk=14, base_def=9, base_spd=16, base_luck=11,
        blurb="A torpedo with teeth. Ambushes from the weeds.",
        evolutions=(
            Evolution("barracuda", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS, grants_skill="vicious_strike"),
            Evolution("pufferfish", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="guppy", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "lobster": Species(
        id="lobster", display_name="Lobster", kind="aquatic",
        base_hp=20, base_atk=14, base_def=14, base_spd=11, base_luck=8,
        blurb="A blue-blooded knight of the deep. Don't grab the claws.",
        evolutions=(
            Evolution("mantis_shrimp", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("pistol_shrimp", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="shrimp", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),

    # avian
    "raven": Species(
        id="raven", display_name="Raven", kind="avian",
        base_hp=18, base_atk=13, base_def=7, base_spd=14, base_luck=10,
        blurb="A black-feathered mastermind. Remembers faces for years.",
        evolutions=(
            Evolution("magpie", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("pigeon", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="sparrow", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "peacock": Species(
        id="peacock", display_name="Peacock", kind="avian",
        base_hp=21, base_atk=12, base_def=11, base_spd=10, base_luck=12,
        blurb="A screaming fan of iridescence. Fearless about its feathers.",
        evolutions=(
            Evolution("cassowary", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("junglefowl", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="chick", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "peregrine_falcon": Species(
        id="peregrine_falcon", display_name="Peregrine Falcon", kind="avian",
        base_hp=17, base_atk=14, base_def=7, base_spd=19, base_luck=11,
        blurb="The fastest animal alive. Drops out of the sky at 240 mph.",
        evolutions=(
            Evolution("red_tailed_hawk", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("barn_owl", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="wren", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "pelican": Species(
        id="pelican", display_name="Pelican", kind="avian",
        base_hp=22, base_atk=11, base_def=13, base_spd=12, base_luck=11,
        blurb="A flying net. That pouch holds more than it looks.",
        evolutions=(
            Evolution("albatross", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("grebe_chick", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="duckling", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),

    # reptile
    "leopard_gecko": Species(
        id="leopard_gecko", display_name="Leopard Gecko", kind="reptile",
        base_hp=18, base_atk=13, base_def=11, base_spd=16, base_luck=12,
        blurb="A spotted nocturnal hunter. Calm, patient, deadly for crickets.",
        evolutions=(
            Evolution("crested_gecko", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("skink_cousin", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="baby_gecko", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "alligator_snapping_turtle": Species(
        id="alligator_snapping_turtle", display_name="Alligator Snapping Turtle", kind="reptile",
        base_hp=25, base_atk=13, base_def=18, base_spd=5, base_luck=8,
        blurb="A prehistoric jaw. Tongue-lure like a worm. Do not investigate.",
        evolutions=(
            Evolution("leatherback_turtle", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("baby_crocodile", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="hatchling_turtle", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "chameleon": Species(
        id="chameleon", display_name="Chameleon", kind="reptile",
        base_hp=19, base_atk=13, base_def=12, base_spd=14, base_luck=11,
        blurb="A color-shifting ambusher. Eyes rotate independently of reality.",
        evolutions=(
            Evolution("jackson_chameleon", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("small_varanid", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="anole", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "komodo_dragon": Species(
        id="komodo_dragon", display_name="Komodo Dragon", kind="reptile",
        base_hp=22, base_atk=16, base_def=13, base_spd=11, base_luck=8,
        blurb="The world's largest lizard. Venom-mouthed, ten feet of trouble.",
        evolutions=(
            Evolution("megalania", requirements={"atk": 28, "spd": 28}, stat_bonus=_TIER_3_BONUS),
            Evolution("fat_tail_lizard", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
        ),
        sprite_fallback="skink", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),

    # ─── tier-3 extensions (Lv 25) ─────────────────────────────────────────
    # Terminal tier-3 forms (lineage stops here).
    "arctic_hare": Species(
        id="arctic_hare", display_name="Arctic Hare", kind="beast",
        base_hp=25, base_atk=11, base_def=10, base_spd=17, base_luck=11,
        blurb="A snow-white survivor. Packs huddle against the cold and never stop moving.",
        evolutions=(Evolution("nuralagus", requirements={"spd": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="rabbit", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "cassowary": Species(
        id="cassowary", display_name="Cassowary", kind="avian",
        base_hp=24, base_atk=14, base_def=12, base_spd=11, base_luck=12,
        blurb="The world's most dangerous bird. Dagger-clawed, flightless, unforgiving.",
        evolutions=(Evolution("ostrich", requirements={"atk": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="chick", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "albatross": Species(
        id="albatross", display_name="Albatross", kind="avian",
        base_hp=25, base_atk=13, base_def=14, base_spd=13, base_luck=12,
        blurb="An ocean-wanderer with an 11-foot wingspan. Goes years without touching land.",
        evolutions=(Evolution("shoebill", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="duckling", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),

    # Continuing tier-3 forms (chain further).
    "leatherback_turtle": Species(
        id="leatherback_turtle", display_name="Leatherback Turtle", kind="reptile",
        base_hp=28, base_atk=14, base_def=21, base_spd=7, base_luck=9,
        blurb="The largest sea turtle. Dives a mile deep in pursuit of jellyfish.",
        evolutions=(Evolution("archelon", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="hatchling_turtle", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "red_tailed_hawk": Species(
        id="red_tailed_hawk", display_name="Red-Tailed Hawk", kind="avian",
        base_hp=20, base_atk=16, base_def=8, base_spd=17, base_luck=12,
        blurb="A soaring opportunist. The cry every Hollywood eagle actually makes.",
        evolutions=(Evolution("golden_eagle", requirements={"spd": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="wren", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "barracuda": Species(
        id="barracuda", display_name="Barracuda", kind="aquatic",
        base_hp=20, base_atk=17, base_def=10, base_spd=19, base_luck=12,
        blurb="A chrome-flanked ambusher. Needle teeth, faster than a thought.",
        evolutions=(Evolution("mako_shark", requirements={"spd": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="guppy", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),

    # ─── tier-4 extensions (Lv 40) ─────────────────────────────────────────
    # Terminal tier-4 (turtle line ends here).
    "archelon": Species(
        id="archelon", display_name="Ancient Sea Turtle", kind="reptile",
        base_hp=33, base_atk=16, base_def=26, base_spd=8, base_luck=10,
        blurb="An extinct fifteen-foot sea turtle from the age of dinosaurs. Walking reef.",
        evolutions=(Evolution("stupendemys", requirements={"def_": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="hatchling_turtle", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),

    # Tier-4 continuing forms for the two flagship lines (raptor + predator fish).
    "golden_eagle": Species(
        id="golden_eagle", display_name="Golden Eagle", kind="avian",
        base_hp=23, base_atk=20, base_def=11, base_spd=19, base_luck=13,
        blurb="A mountain hunter with a seven-foot wingspan. Takes foxes and wolves whole.",
        evolutions=(Evolution("harpy_eagle", requirements={"atk": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="wren", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "mako_shark": Species(
        id="mako_shark", display_name="Mako Shark", kind="aquatic",
        base_hp=23, base_atk=21, base_def=13, base_spd=22, base_luck=13,
        blurb="The fastest shark alive. Breaches like a missile, outruns its own prey.",
        evolutions=(Evolution("great_white_shark", requirements={"spd": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="guppy", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),

    # ant line tier-3 / tier-4 extensions
    "bullet_ant": Species(
        id="bullet_ant", display_name="Bullet Ant", kind="insect",
        base_hp=24, base_atk=18, base_def=15, base_spd=12, base_luck=8,
        blurb="The most painful sting on record. One is an event; a nest is a catastrophe.",
        evolutions=(Evolution("titanomyrma", requirements={"atk": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="ant", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "titanomyrma": Species(
        id="titanomyrma", display_name="Giant Prehistoric Ant", kind="insect",
        base_hp=30, base_atk=22, base_def=18, base_spd=10, base_luck=9,
        blurb="The largest ant that ever lived. Prehistoric queen with a 15cm wingspan.",
        evolutions=(
            Evolution("winged_queen", requirements={"int_": 62, "luck": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("atlas_beetle", requirements={"hp": 62, "def_": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="ant", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),

    # ─── 5-tier extensions (depth-3 lineages grow to depth 5) ──────────────
    # beasts
    "beaver": Species(
        id="beaver", display_name="Beaver", kind="beast",
        base_hp=26, base_atk=11, base_def=13, base_spd=9, base_luck=12,
        blurb="A river architect. Engineer of dams, carpenter of the wild.",
        evolutions=(Evolution("giant_beaver", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="field_mouse", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "giant_beaver": Species(
        id="giant_beaver", display_name="Giant Beaver", kind="beast",
        base_hp=32, base_atk=14, base_def=16, base_spd=9, base_luck=12,
        blurb="An extinct bear-sized rodent. Once dammed entire river valleys.",
        evolutions=(Evolution("phoberomys", requirements={"def_": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="field_mouse", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "prairie_dog": Species(
        id="prairie_dog", display_name="Prairie Dog", kind="beast",
        base_hp=24, base_atk=12, base_def=12, base_spd=12, base_luck=13,
        blurb="A colonial strategist. Its burrow network is a city, and its call is a language.",
        evolutions=(Evolution("chinese_giant_squirrel", requirements={"luck": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="squirrel", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "chinese_giant_squirrel": Species(
        id="chinese_giant_squirrel", display_name="Chinese Giant Squirrel", kind="beast",
        base_hp=28, base_atk=16, base_def=12, base_spd=15, base_luck=13,
        blurb="The largest tree squirrel alive. Runs along branches like a rope-walker.",
        evolutions=(
            Evolution("cloud_squirrel", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("ironclad_squirrel", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="squirrel", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "armadillo": Species(
        id="armadillo", display_name="Armadillo", kind="beast",
        base_hp=28, base_atk=10, base_def=20, base_spd=8, base_luck=9,
        blurb="A rolling fortress. Bulletproof when curled, indifferent to danger.",
        evolutions=(Evolution("glyptodon", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="hedgehog", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "glyptodon": Species(
        id="glyptodon", display_name="Tank Armadillo", kind="beast",
        base_hp=34, base_atk=13, base_def=25, base_spd=7, base_luck=10,
        blurb="An extinct car-sized armadillo. Solid bone dome over a tank.",
        evolutions=(Evolution("doedicurus", requirements={"def_": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="hedgehog", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),

    # insects
    "velvet_ant": Species(
        id="velvet_ant", display_name="Velvet Ant", kind="insect",
        base_hp=19, base_atk=22, base_def=9, base_spd=19, base_luck=8,
        blurb="Not an ant — a wingless wasp known as 'cow killer' for its sting.",
        evolutions=(Evolution("tarantula_hawk", requirements={"atk": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="bee", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "tarantula_hawk": Species(
        id="tarantula_hawk", display_name="Tarantula Hawk", kind="insect",
        base_hp=22, base_atk=27, base_def=11, base_spd=23, base_luck=9,
        blurb="A wasp that hunts tarantulas. Its sting rates a 4 on the pain index.",
        evolutions=(
            Evolution("venom_general", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("carapace_scout", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="bee", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "hercules_beetle": Species(
        id="hercules_beetle", display_name="Hercules Beetle", kind="insect",
        base_hp=23, base_atk=17, base_def=17, base_spd=9, base_luck=12,
        blurb="A horn as long as its body. Can lift enormous weights for its size.",
        evolutions=(Evolution("goliath_beetle", requirements={"atk": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="ladybug", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "goliath_beetle": Species(
        id="goliath_beetle", display_name="Goliath Beetle", kind="insect",
        base_hp=28, base_atk=21, base_def=20, base_spd=10, base_luck=13,
        blurb="The heaviest insect alive. Pound-for-pound, the strongest creature on earth.",
        evolutions=(Evolution("arthropleura", requirements={"atk": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="ladybug", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "hercules_moth": Species(
        id="hercules_moth", display_name="Hercules Moth", kind="insect",
        base_hp=26, base_atk=9, base_def=16, base_spd=10, base_luck=11,
        blurb="A 27cm wingspan. Flies silently through a tropical night.",
        evolutions=(Evolution("white_witch_moth", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="caterpillar", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "white_witch_moth": Species(
        id="white_witch_moth", display_name="White Witch Moth", kind="insect",
        base_hp=30, base_atk=11, base_def=19, base_spd=12, base_luck=13,
        blurb="The largest wingspan of any moth — 30cm across, a ghost on the wing.",
        evolutions=(Evolution("meganeura", requirements={"def_": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="caterpillar", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),

    # amphibians
    "beelzebufo": Species(
        id="beelzebufo", display_name="Devil Frog", kind="amphibian",
        base_hp=25, base_atk=17, base_def=16, base_spd=13, base_luck=10,
        blurb="The 'devil frog' — extinct, ten pounds, devoured dinosaur hatchlings.",
        evolutions=(Evolution("koolasuchus", requirements={"atk": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="tadpole", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "koolasuchus": Species(
        id="koolasuchus", display_name="Armored Giant Salamander", kind="amphibian",
        base_hp=30, base_atk=21, base_def=19, base_spd=13, base_luck=11,
        blurb="An extinct crocodile-shaped amphibian. Apex of its river for millions of years.",
        evolutions=(Evolution("prionosuchus", requirements={"atk": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="tadpole", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "poison_dart_frog": Species(
        id="poison_dart_frog", display_name="Poison Dart Frog", kind="amphibian",
        base_hp=24, base_atk=17, base_def=14, base_spd=13, base_luck=12,
        blurb="A jewel-bright warning. One lick would floor a hunter ten times its size.",
        evolutions=(Evolution("golden_poison_frog", requirements={"atk": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="froglet", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "golden_poison_frog": Species(
        id="golden_poison_frog", display_name="Golden Poison Frog", kind="amphibian",
        base_hp=28, base_atk=21, base_def=16, base_spd=14, base_luck=14,
        blurb="The most toxic vertebrate alive. A single frog could kill a hundred men.",
        evolutions=(
            Evolution("sky_toad", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("stone_toad", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="froglet", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "mudpuppy": Species(
        id="mudpuppy", display_name="Mudpuppy", kind="amphibian",
        base_hp=27, base_atk=13, base_def=17, base_spd=10, base_luck=12,
        blurb="A gilled river salamander. Never grows up, never stops hunting.",
        evolutions=(Evolution("japanese_giant_salamander", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="newt", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "japanese_giant_salamander": Species(
        id="japanese_giant_salamander", display_name="Japanese Giant Salamander", kind="amphibian",
        base_hp=33, base_atk=16, base_def=21, base_spd=10, base_luck=13,
        blurb="Five feet long, called 'giant pepper fish' for the milky ooze it weeps when alarmed.",
        evolutions=(
            Evolution("river_king_salamander", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("mountain_salamander", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="newt", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "waterdog": Species(
        id="waterdog", display_name="Waterdog", kind="amphibian",
        base_hp=27, base_atk=14, base_def=17, base_spd=10, base_luck=13,
        blurb="A larval giant salamander. Gilled and patient, a killer in a pond.",
        evolutions=(Evolution("chinese_giant_salamander", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="axolotl", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "chinese_giant_salamander": Species(
        id="chinese_giant_salamander", display_name="Chinese Giant Salamander", kind="amphibian",
        base_hp=33, base_atk=17, base_def=21, base_spd=10, base_luck=14,
        blurb="The largest living amphibian. Six feet of slow-river menace.",
        evolutions=(
            Evolution("thunder_axolotl", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("stone_axolotl", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="axolotl", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),

    # aquatic
    "arapaima": Species(
        id="arapaima", display_name="Arapaima", kind="aquatic",
        base_hp=24, base_atk=16, base_def=14, base_spd=17, base_luck=10,
        blurb="A 15-foot armored Amazon river fish. Surfaces to breathe like a whale.",
        evolutions=(Evolution("beluga_sturgeon", requirements={"spd": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="minnow", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "beluga_sturgeon": Species(
        id="beluga_sturgeon", display_name="Beluga Sturgeon", kind="aquatic",
        base_hp=30, base_atk=20, base_def=17, base_spd=19, base_luck=11,
        blurb="A 24-foot river giant. Living fossil, older than whole continents.",
        evolutions=(Evolution("leedsichthys", requirements={"atk": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="minnow", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "triton_shell": Species(
        id="triton_shell", display_name="Triton Shell", kind="aquatic",
        base_hp=28, base_atk=9, base_def=22, base_spd=3, base_luck=10,
        blurb="A predatory sea snail. Hunts starfish with an acidic proboscis.",
        evolutions=(Evolution("giant_pacific_octopus", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="snail", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "giant_pacific_octopus": Species(
        id="giant_pacific_octopus", display_name="Giant Pacific Octopus", kind="aquatic",
        base_hp=26, base_atk=16, base_def=13, base_spd=14, base_luck=15,
        blurb="A 15-foot shape-shifter with eight problem-solving arms.",
        evolutions=(Evolution("giant_squid", requirements={"atk": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="snail", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "mantis_shrimp": Species(
        id="mantis_shrimp", display_name="Mantis Shrimp", kind="aquatic",
        base_hp=23, base_atk=19, base_def=13, base_spd=18, base_luck=11,
        blurb="Strikes with the speed of a bullet. Sees colors you can't imagine.",
        evolutions=(Evolution("coconut_crab", requirements={"atk": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="shrimp", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "coconut_crab": Species(
        id="coconut_crab", display_name="Coconut Crab", kind="aquatic",
        base_hp=28, base_atk=24, base_def=17, base_spd=13, base_luck=11,
        blurb="The largest terrestrial arthropod. Cracks coconuts with those claws.",
        evolutions=(Evolution("eurypterid", requirements={"atk": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="shrimp", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),

    # avian
    "magpie": Species(
        id="magpie", display_name="Magpie", kind="avian",
        base_hp=21, base_atk=15, base_def=9, base_spd=16, base_luck=13,
        blurb="A glint-thief corvid. Remembers which humans have wronged it and tells the flock.",
        evolutions=(Evolution("thick_billed_raven", requirements={"spd": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="sparrow", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "thick_billed_raven": Species(
        id="thick_billed_raven", display_name="Thick-Billed Raven", kind="avian",
        base_hp=26, base_atk=19, base_def=11, base_spd=18, base_luck=14,
        blurb="The largest corvid alive. An Ethiopian highland oracle with a stone-cracking beak.",
        evolutions=(Evolution("teratornis", requirements={"atk": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="sparrow", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "ostrich": Species(
        id="ostrich", display_name="Ostrich", kind="avian",
        base_hp=30, base_atk=19, base_def=14, base_spd=18, base_luck=13,
        blurb="The largest bird on earth. Runs at 45 mph and kicks hard enough to kill a lion.",
        evolutions=(Evolution("elephant_bird", requirements={"atk": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="chick", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "shoebill": Species(
        id="shoebill", display_name="Shoebill", kind="avian",
        base_hp=29, base_atk=18, base_def=17, base_spd=14, base_luck=13,
        blurb="A stork-heron oddity with a clog for a beak. Stares like a nightmare.",
        evolutions=(Evolution("argentavis", requirements={"atk": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="duckling", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),

    # reptile
    "crested_gecko": Species(
        id="crested_gecko", display_name="Crested Gecko", kind="reptile",
        base_hp=22, base_atk=16, base_def=14, base_spd=19, base_luck=14,
        blurb="A branch-dweller with eyelash-spikes. Thought extinct until 1994.",
        evolutions=(Evolution("new_caledonian_giant_gecko", requirements={"spd": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="baby_gecko", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "new_caledonian_giant_gecko": Species(
        id="new_caledonian_giant_gecko", display_name="New Caledonian Giant Gecko", kind="reptile",
        base_hp=28, base_atk=20, base_def=17, base_spd=21, base_luck=15,
        blurb="The largest gecko alive. Fifteen inches of island apex predator.",
        evolutions=(
            Evolution("canopy_gecko_king", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("stone_gecko_elder", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="baby_gecko", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "jackson_chameleon": Species(
        id="jackson_chameleon", display_name="Jackson's Chameleon", kind="reptile",
        base_hp=23, base_atk=16, base_def=15, base_spd=17, base_luck=13,
        blurb="Three horns on the face of a male. Slow, deliberate, patient.",
        evolutions=(Evolution("parson_chameleon", requirements={"spd": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="anole", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "parson_chameleon": Species(
        id="parson_chameleon", display_name="Parson's Chameleon", kind="reptile",
        base_hp=28, base_atk=20, base_def=18, base_spd=18, base_luck=14,
        blurb="The heaviest chameleon. Lives for a decade in the Madagascar canopy.",
        evolutions=(
            Evolution("mirage_chameleon", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("fortress_chameleon", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="anole", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "megalania": Species(
        id="megalania", display_name="Giant Monitor Lizard", kind="reptile",
        base_hp=27, base_atk=21, base_def=17, base_spd=13, base_luck=9,
        blurb="An extinct 23-foot monitor lizard. The largest goanna that ever walked Australia.",
        evolutions=(Evolution("mosasaur", requirements={"atk": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="skink", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "mosasaur": Species(
        id="mosasaur", display_name="Prehistoric Sea Lizard", kind="reptile",
        base_hp=33, base_atk=25, base_def=20, base_spd=15, base_luck=10,
        blurb="An extinct sea-lizard, 50 feet long. Apex predator of the late cretaceous oceans.",
        evolutions=(Evolution("tylosaurus", requirements={"atk": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="skink", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),

    # lagomorph apex continuation
    "nuralagus": Species(
        id="nuralagus", display_name="Island Giant Rabbit", kind="beast",
        base_hp=30, base_atk=13, base_def=13, base_spd=18, base_luck=12,
        blurb="An extinct fox-sized rabbit from Minorca. Slow-hopping, no predators, unafraid.",
        evolutions=(
            Evolution("tundra_lynx", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("yeti_hare", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="rabbit", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),

    # ─── 7-tier flagship extensions (wren + guppy) ─────────────────────────
    "harpy_eagle": Species(
        id="harpy_eagle", display_name="Harpy Eagle", kind="avian",
        base_hp=28, base_atk=25, base_def=13, base_spd=21, base_luck=14,
        blurb="The strongest eagle alive. Plucks monkeys from the jungle canopy like fruit.",
        evolutions=(Evolution("haast_eagle", requirements={"atk": 80}, stat_bonus=_TIER_6_BONUS),),
        sprite_fallback="wren", is_starter=False, evolves_at=TIER_6_LEVEL,
    ),
    "haast_eagle": Species(
        id="haast_eagle", display_name="Haast's Eagle", kind="avian",
        base_hp=34, base_atk=31, base_def=16, base_spd=24, base_luck=16,
        blurb="The largest eagle ever to exist. Hunted moa, extinct only 500 years.",
        evolutions=(
            Evolution("thunder_eagle", requirements={"atk": 100, "spd": 100}, stat_bonus=_TIER_7_BONUS),
            Evolution("shadow_eagle", requirements={"def_": 100, "res": 100}, stat_bonus=_TIER_7_BONUS),
        ),
        sprite_fallback="wren", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "great_white_shark": Species(
        id="great_white_shark", display_name="Great White Shark", kind="aquatic",
        base_hp=28, base_atk=27, base_def=17, base_spd=26, base_luck=14,
        blurb="Apex of the open ocean. Three rows of teeth and no reason to prove anything.",
        evolutions=(Evolution("megalodon", requirements={"atk": 80}, stat_bonus=_TIER_6_BONUS),),
        sprite_fallback="guppy", is_starter=False, evolves_at=TIER_6_LEVEL,
    ),
    "megalodon": Species(
        id="megalodon", display_name="Megalodon", kind="aquatic",
        base_hp=34, base_atk=34, base_def=21, base_spd=29, base_luck=16,
        blurb="An extinct 60-foot shark. Ate whales whole. There is nothing after this.",
        evolutions=(
            Evolution("storm_megalodon", requirements={"atk": 100, "spd": 100}, stat_bonus=_TIER_7_BONUS),
            Evolution("basalt_megalodon", requirements={"def_": 100, "res": 100}, stat_bonus=_TIER_7_BONUS),
        ),
        sprite_fallback="guppy", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),

    # ─── tier-5 extensions (Lv 55) ─────────────────────────────────────────
    # Prehistoric / extinct giants; each continues to a tier-6 terminal apex.
    "phoberomys": Species(
        id="phoberomys", display_name="Ancient Giant Rodent", kind="beast",
        base_hp=36, base_atk=16, base_def=18, base_spd=10, base_luck=13,
        blurb="A prehistoric rodent the size of a buffalo. Roamed the Venezuelan wetlands.",
        evolutions=(Evolution("josephoartigasia", requirements={"def_": 80}, stat_bonus=_TIER_6_BONUS),),
        sprite_fallback="field_mouse", is_starter=False, evolves_at=TIER_6_LEVEL,
    ),
    "doedicurus": Species(
        id="doedicurus", display_name="Mace-Tailed Armadillo", kind="beast",
        base_hp=38, base_atk=17, base_def=28, base_spd=8, base_luck=11,
        blurb="An extinct armored giant. Tail ended in a spiked mace for dueling its own kind.",
        evolutions=(Evolution("megatherium", requirements={"def_": 80}, stat_bonus=_TIER_6_BONUS),),
        sprite_fallback="hedgehog", is_starter=False, evolves_at=TIER_6_LEVEL,
    ),
    "arthropleura": Species(
        id="arthropleura", display_name="Giant Millipede", kind="insect",
        base_hp=32, base_atk=24, base_def=23, base_spd=11, base_luck=14,
        blurb="An eight-foot-long prehistoric millipede. Rolled through the carboniferous forest.",
        evolutions=(Evolution("pulmonoscorpius", requirements={"atk": 80}, stat_bonus=_TIER_6_BONUS),),
        sprite_fallback="ladybug", is_starter=False, evolves_at=TIER_6_LEVEL,
    ),
    "meganeura": Species(
        id="meganeura", display_name="Ancient Dragonfly", kind="insect",
        base_hp=33, base_atk=14, base_def=22, base_spd=14, base_luck=14,
        blurb="A griffinfly with a 75cm wingspan. Apex insect hunter of the Carboniferous.",
        evolutions=(Evolution("meganeuropsis", requirements={"def_": 80}, stat_bonus=_TIER_6_BONUS),),
        sprite_fallback="caterpillar", is_starter=False, evolves_at=TIER_6_LEVEL,
    ),
    "prionosuchus": Species(
        id="prionosuchus", display_name="Crocodile Salamander", kind="amphibian",
        base_hp=34, base_atk=24, base_def=22, base_spd=14, base_luck=12,
        blurb="A 9-meter extinct amphibian shaped like a crocodile. Patrolled Permian rivers.",
        evolutions=(Evolution("mastodonsaurus", requirements={"atk": 80}, stat_bonus=_TIER_6_BONUS),),
        sprite_fallback="tadpole", is_starter=False, evolves_at=TIER_6_LEVEL,
    ),
    "leedsichthys": Species(
        id="leedsichthys", display_name="Leviathan Fish", kind="aquatic",
        base_hp=34, base_atk=23, base_def=20, base_spd=21, base_luck=12,
        blurb="A 50-foot Jurassic bony fish. Filter-feeding giant, bigger than any whale shark.",
        evolutions=(Evolution("dunkleosteus", requirements={"atk": 80}, stat_bonus=_TIER_6_BONUS),),
        sprite_fallback="minnow", is_starter=False, evolves_at=TIER_6_LEVEL,
    ),
    "giant_squid": Species(
        id="giant_squid", display_name="Giant Squid", kind="aquatic",
        base_hp=30, base_atk=21, base_def=16, base_spd=17, base_luck=17,
        blurb="A 40-foot kraken of the deep. Hunts sperm whales in water humans can't reach.",
        evolutions=(Evolution("colossal_squid", requirements={"atk": 80}, stat_bonus=_TIER_6_BONUS),),
        sprite_fallback="snail", is_starter=False, evolves_at=TIER_6_LEVEL,
    ),
    "eurypterid": Species(
        id="eurypterid", display_name="Sea Scorpion", kind="aquatic",
        base_hp=32, base_atk=26, base_def=20, base_spd=15, base_luck=12,
        blurb="An extinct aquatic arthropod. Claws, armor, and a scorpion's patience.",
        evolutions=(Evolution("jaekelopterus", requirements={"atk": 80}, stat_bonus=_TIER_6_BONUS),),
        sprite_fallback="shrimp", is_starter=False, evolves_at=TIER_6_LEVEL,
    ),
    "teratornis": Species(
        id="teratornis", display_name="Giant Vulture", kind="avian",
        base_hp=30, base_atk=22, base_def=14, base_spd=21, base_luck=15,
        blurb="An extinct 4-meter-wingspan scavenger. Circled the Ice Age skies.",
        evolutions=(Evolution("phorusrhacos", requirements={"atk": 80}, stat_bonus=_TIER_6_BONUS),),
        sprite_fallback="sparrow", is_starter=False, evolves_at=TIER_6_LEVEL,
    ),
    "elephant_bird": Species(
        id="elephant_bird", display_name="Elephant Bird", kind="avian",
        base_hp=36, base_atk=22, base_def=17, base_spd=20, base_luck=14,
        blurb="A 10-foot flightless Madagascar giant. Its egg was a gallon of yolk.",
        evolutions=(Evolution("moa", requirements={"atk": 80}, stat_bonus=_TIER_6_BONUS),),
        sprite_fallback="chick", is_starter=False, evolves_at=TIER_6_LEVEL,
    ),
    "argentavis": Species(
        id="argentavis", display_name="Giant Teratorn", kind="avian",
        base_hp=33, base_atk=21, base_def=19, base_spd=22, base_luck=14,
        blurb="The largest flying bird ever — a 7-meter wingspan soaring over ancient Argentina.",
        evolutions=(Evolution("pelagornis", requirements={"spd": 80}, stat_bonus=_TIER_6_BONUS),),
        sprite_fallback="duckling", is_starter=False, evolves_at=TIER_6_LEVEL,
    ),
    "stupendemys": Species(
        id="stupendemys", display_name="Giant River Turtle", kind="reptile",
        base_hp=40, base_atk=19, base_def=30, base_spd=9, base_luck=11,
        blurb="A prehistoric 4-meter river turtle. Ate giant crocodiles for breakfast.",
        evolutions=(Evolution("meiolania", requirements={"def_": 80}, stat_bonus=_TIER_6_BONUS),),
        sprite_fallback="hatchling_turtle", is_starter=False, evolves_at=TIER_6_LEVEL,
    ),
    "tylosaurus": Species(
        id="tylosaurus", display_name="Ancient Sea Dragon", kind="reptile",
        base_hp=38, base_atk=29, base_def=23, base_spd=18, base_luck=11,
        blurb="An extinct 14-meter mosasaur. Ruled the cretaceous inland seas.",
        evolutions=(Evolution("liopleurodon", requirements={"atk": 80}, stat_bonus=_TIER_6_BONUS),),
        sprite_fallback="skink", is_starter=False, evolves_at=TIER_6_LEVEL,
    ),

    # ─── tier-6 terminal apex forms (Lv 75+) ───────────────────────────────
    # End of the real-animal chain; mythic is the only thing past here.
    "josephoartigasia": Species(
        id="josephoartigasia", display_name="Titan Rodent", kind="beast",
        base_hp=42, base_atk=20, base_def=22, base_spd=12, base_luck=14,
        blurb="The largest rodent that ever lived — over a ton, the size of a bull.",
        evolutions=(
            Evolution("titan_rat_king", requirements={"atk": 100, "spd": 100}, stat_bonus=_TIER_7_BONUS),
            Evolution("burrow_emperor", requirements={"def_": 100, "res": 100}, stat_bonus=_TIER_7_BONUS),
        ),
        sprite_fallback="field_mouse", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "megatherium": Species(
        id="megatherium", display_name="Giant Ground Sloth", kind="beast",
        base_hp=45, base_atk=22, base_def=33, base_spd=8, base_luck=13,
        blurb="A 20-foot Ice Age sloth the weight of an elephant. Clawed its lunch out of trees.",
        evolutions=(
            Evolution("thunder_sloth", requirements={"atk": 100, "spd": 100}, stat_bonus=_TIER_7_BONUS),
            Evolution("bedrock_sloth", requirements={"def_": 100, "res": 100}, stat_bonus=_TIER_7_BONUS),
        ),
        sprite_fallback="hedgehog", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "pulmonoscorpius": Species(
        id="pulmonoscorpius", display_name="Giant Land Scorpion", kind="insect",
        base_hp=38, base_atk=30, base_def=26, base_spd=13, base_luck=15,
        blurb="A meter-long prehistoric land scorpion. Lung-breathers from before there were birds.",
        evolutions=(
            Evolution("storm_scorpion", requirements={"atk": 100, "spd": 100}, stat_bonus=_TIER_7_BONUS),
            Evolution("obelisk_scorpion", requirements={"def_": 100, "res": 100}, stat_bonus=_TIER_7_BONUS),
        ),
        sprite_fallback="ladybug", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "meganeuropsis": Species(
        id="meganeuropsis", display_name="Titan Dragonfly", kind="insect",
        base_hp=39, base_atk=18, base_def=26, base_spd=17, base_luck=15,
        blurb="The largest insect that ever lived — 71cm of iridescent, silent death.",
        evolutions=(
            Evolution("thunder_dragonfly", requirements={"atk": 100, "spd": 100}, stat_bonus=_TIER_7_BONUS),
            Evolution("fossil_dragonfly", requirements={"def_": 100, "res": 100}, stat_bonus=_TIER_7_BONUS),
        ),
        sprite_fallback="caterpillar", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "mastodonsaurus": Species(
        id="mastodonsaurus", display_name="Jaw-Tooth Amphibian", kind="amphibian",
        base_hp=40, base_atk=30, base_def=26, base_spd=16, base_luck=14,
        blurb="A 6-meter extinct amphibian with tusks that pierced its own skull to fit shut.",
        evolutions=(
            Evolution("thunder_toad", requirements={"atk": 100, "spd": 100}, stat_bonus=_TIER_7_BONUS),
            Evolution("basalt_toad", requirements={"def_": 100, "res": 100}, stat_bonus=_TIER_7_BONUS),
        ),
        sprite_fallback="tadpole", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "dunkleosteus": Species(
        id="dunkleosteus", display_name="Armored Prehistoric Fish", kind="aquatic",
        base_hp=40, base_atk=31, base_def=25, base_spd=24, base_luck=13,
        blurb="A Devonian armored fish with self-sharpening blade-plates for teeth.",
        evolutions=(
            Evolution("apex_kraken_fish", requirements={"atk": 100, "spd": 100}, stat_bonus=_TIER_7_BONUS),
            Evolution("armored_leviathan", requirements={"def_": 100, "res": 100}, stat_bonus=_TIER_7_BONUS),
        ),
        sprite_fallback="minnow", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "colossal_squid": Species(
        id="colossal_squid", display_name="Colossal Squid", kind="aquatic",
        base_hp=36, base_atk=27, base_def=20, base_spd=20, base_luck=19,
        blurb="Bigger than a giant squid. Swivel hooks on each arm. Eyes the size of dinner plates.",
        evolutions=(
            Evolution("thunder_squid", requirements={"atk": 100, "spd": 100}, stat_bonus=_TIER_7_BONUS),
            Evolution("abyss_squid", requirements={"def_": 100, "res": 100}, stat_bonus=_TIER_7_BONUS),
        ),
        sprite_fallback="snail", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "jaekelopterus": Species(
        id="jaekelopterus", display_name="Giant Sea Scorpion", kind="aquatic",
        base_hp=38, base_atk=32, base_def=24, base_spd=18, base_luck=14,
        blurb="The largest arthropod that ever lived — 2.5 meters of aquatic pincer.",
        evolutions=(
            Evolution("storm_euryp", requirements={"atk": 100, "spd": 100}, stat_bonus=_TIER_7_BONUS),
            Evolution("cavern_euryp", requirements={"def_": 100, "res": 100}, stat_bonus=_TIER_7_BONUS),
        ),
        sprite_fallback="shrimp", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "phorusrhacos": Species(
        id="phorusrhacos", display_name="Terror Bird", kind="avian",
        base_hp=36, base_atk=29, base_def=17, base_spd=24, base_luck=16,
        blurb="A 3-meter flightless carnivore with a beak like an axe. South America's nightmare.",
        evolutions=(
            Evolution("thunder_runner", requirements={"atk": 100, "spd": 100}, stat_bonus=_TIER_7_BONUS),
            Evolution("bedrock_runner", requirements={"def_": 100, "res": 100}, stat_bonus=_TIER_7_BONUS),
        ),
        sprite_fallback="sparrow", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "moa": Species(
        id="moa", display_name="Moa", kind="avian",
        base_hp=42, base_atk=27, base_def=21, base_spd=22, base_luck=15,
        blurb="A 12-foot flightless giant from New Zealand. Extinct within 100 years of human arrival.",
        evolutions=(
            Evolution("thunder_moa", requirements={"atk": 100, "spd": 100}, stat_bonus=_TIER_7_BONUS),
            Evolution("basalt_moa", requirements={"def_": 100, "res": 100}, stat_bonus=_TIER_7_BONUS),
        ),
        sprite_fallback="chick", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "pelagornis": Species(
        id="pelagornis", display_name="Toothed Giant Seabird", kind="avian",
        base_hp=38, base_atk=26, base_def=22, base_spd=25, base_luck=15,
        blurb="A 7-meter wingspan and a beak lined with bony 'teeth'. Extinct 3 million years.",
        evolutions=(
            Evolution("thunder_seabird", requirements={"atk": 100, "spd": 100}, stat_bonus=_TIER_7_BONUS),
            Evolution("cavern_seabird", requirements={"def_": 100, "res": 100}, stat_bonus=_TIER_7_BONUS),
        ),
        sprite_fallback="duckling", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "meiolania": Species(
        id="meiolania", display_name="Horned Giant Turtle", kind="reptile",
        base_hp=46, base_atk=24, base_def=35, base_spd=10, base_luck=12,
        blurb="An extinct island turtle with horns on its skull and a spiked club tail.",
        evolutions=(
            Evolution("titan_reef_turtle", requirements={"atk": 100, "spd": 100}, stat_bonus=_TIER_7_BONUS),
            Evolution("fortress_shell", requirements={"def_": 100, "res": 100}, stat_bonus=_TIER_7_BONUS),
        ),
        sprite_fallback="hatchling_turtle", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "liopleurodon": Species(
        id="liopleurodon", display_name="Giant Marine Reptile", kind="reptile",
        base_hp=44, base_atk=34, base_def=27, base_spd=20, base_luck=12,
        blurb="A 7-meter Jurassic pliosaur. Crocodile-headed terror of the ancient oceans.",
        evolutions=(
            Evolution("thunder_mosasaur", requirements={"atk": 100, "spd": 100}, stat_bonus=_TIER_7_BONUS),
            Evolution("bedrock_pliosaur", requirements={"def_": 100, "res": 100}, stat_bonus=_TIER_7_BONUS),
        ),
        sprite_fallback="skink", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),

    # ─── ant line — cross-kind branches into beetles ───────────────────────
    # The ant lineage can branch mid-chain into a beetle form, giving DEF/INT
    # players a different insect body plan. All still kind="insect" so the
    # color remains yellow, but the display name and (future) art differ.
    "scarab_beetle": Species(
        id="scarab_beetle", display_name="Scarab Beetle", kind="insect",
        base_hp=18, base_atk=10, base_def=18, base_spd=7, base_luck=9,
        blurb="An armored digger that rolls dung into little suns.",
        evolutions=(Evolution("stag_beetle_giant", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="ant", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "winged_queen": Species(
        id="winged_queen", display_name="Winged Queen Ant", kind="insect",
        base_hp=32, base_atk=24, base_def=20, base_spd=14, base_luck=13,
        blurb="A founder matriarch with a coronet of wings. Starts new colonies from the air.",
        sprite_fallback="ant", is_starter=False,
    ),
    "atlas_beetle": Species(
        id="atlas_beetle", display_name="Atlas Beetle", kind="insect",
        base_hp=40, base_atk=22, base_def=28, base_spd=8, base_luck=10,
        blurb="A horned giant with plated armor. Lifts a hundred times its weight without flinching.",
        sprite_fallback="ant", is_starter=False,
    ),

    # ─── ant line — beetle subtree (parallel to titanomyrma subtree) ───────
    # scarab_beetle's own evolution path: tier 4 stag_beetle_giant branches
    # at tier 4 into two tier-5 beetle apex forms. No convergence back into
    # the ant subtree — buddies that went beetle at tier 3 stay beetles.
    "stag_beetle_giant": Species(
        id="stag_beetle_giant", display_name="Giant Stag Beetle", kind="insect",
        base_hp=26, base_atk=16, base_def=22, base_spd=9, base_luck=9,
        blurb="A head-long duelist with mandibles as long as its body.",
        evolutions=(
            Evolution("horned_colossus", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("iron_carapace", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="ant", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "horned_colossus": Species(
        id="horned_colossus", display_name="Horned Colossus Beetle", kind="insect",
        base_hp=36, base_atk=30, base_def=24, base_spd=12, base_luck=11,
        blurb="A prehistoric beetle with a rhino horn. Charges straight through whatever's in the way.",
        sprite_fallback="ant", is_starter=False,
    ),
    "iron_carapace": Species(
        id="iron_carapace", display_name="Iron Carapace Beetle", kind="insect",
        base_hp=42, base_atk=18, base_def=34, base_spd=7, base_luck=10,
        blurb="Plated like a castle door. Nothing gets in, including time.",
        sprite_fallback="ant", is_starter=False,
    ),

    # ═════════════════════════════════════════════════════════════════════
    # Split-and-converge rework — batch 1: rabbit, tadpole, hatchling_turtle,
    # minnow, wren. Each lineage gets branches at tier 2 and at its apex,
    # with a short cross-kind side path and divergent terminal apex forms.
    # ═════════════════════════════════════════════════════════════════════

    # ─── rabbit lineage (depth 5) ─────────────────────────────────────────
    "marsh_pika": Species(
        id="marsh_pika", display_name="Marsh Pika", kind="beast",
        base_hp=22, base_atk=9, base_def=14, base_spd=12, base_luck=11,
        blurb="A stocky alpine cousin. Hoards hay and holds territory with squeaks.",
        evolutions=(Evolution("giant_pika", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="rabbit", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "giant_pika": Species(
        id="giant_pika", display_name="Giant Pika", kind="beast",
        base_hp=28, base_atk=12, base_def=17, base_spd=13, base_luck=12,
        blurb="A prehistoric rock-dweller the size of a wild boar.",
        evolutions=(
            Evolution("pika_ram", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("stone_pika", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="rabbit", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "tundra_lynx": Species(
        id="tundra_lynx", display_name="Tundra Lynx", kind="beast",
        base_hp=34, base_atk=22, base_def=16, base_spd=24, base_luck=14,
        blurb="A snow-pawed sprint hunter with tufted ears and silent feet.",
        sprite_fallback="rabbit", is_starter=False,
    ),
    "yeti_hare": Species(
        id="yeti_hare", display_name="Yeti Hare", kind="beast",
        base_hp=40, base_atk=16, base_def=26, base_spd=14, base_luck=13,
        blurb="A shaggy mountain giant. Unbothered by blizzards and reasonable arguments.",
        sprite_fallback="rabbit", is_starter=False,
    ),
    "pika_ram": Species(
        id="pika_ram", display_name="Pika Ram", kind="beast",
        base_hp=34, base_atk=24, base_def=15, base_spd=22, base_luck=13,
        blurb="A horned high-altitude brawler. Charges over scree like it's flat.",
        sprite_fallback="rabbit", is_starter=False,
    ),
    "stone_pika": Species(
        id="stone_pika", display_name="Stone Pika", kind="beast",
        base_hp=42, base_atk=14, base_def=28, base_spd=12, base_luck=14,
        blurb="A granite-fleshed boulder of a rodent. Rolls out the welcome mat, then rolls over you.",
        sprite_fallback="rabbit", is_starter=False,
    ),

    # ─── tadpole lineage (depth 7, tier-3 short branch + tier-7 apex branch) ─
    "axolot_serpent": Species(
        id="axolot_serpent", display_name="Serpent Axolotl", kind="amphibian",
        base_hp=22, base_atk=13, base_def=15, base_spd=13, base_luck=10,
        blurb="A long-bodied branch of the salamander tree. Slithers more than it hops.",
        evolutions=(Evolution("sea_eel", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="tadpole", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "sea_eel": Species(
        id="sea_eel", display_name="Sea Eel", kind="amphibian",
        base_hp=26, base_atk=17, base_def=17, base_spd=16, base_luck=11,
        blurb="A river-to-ocean rogue. Electric through the dark.",
        evolutions=(
            Evolution("electric_eel_king", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("mud_basilisk", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="tadpole", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "electric_eel_king": Species(
        id="electric_eel_king", display_name="Electric Eel King", kind="amphibian",
        base_hp=32, base_atk=26, base_def=19, base_spd=24, base_luck=13,
        blurb="A three-meter bolt of stored lightning. One touch stuns a horse.",
        sprite_fallback="tadpole", is_starter=False,
    ),
    "mud_basilisk": Species(
        id="mud_basilisk", display_name="Mud Basilisk", kind="amphibian",
        base_hp=38, base_atk=18, base_def=28, base_spd=15, base_luck=14,
        blurb="A river-bottom hunter with armor plates and an unblinking stare.",
        sprite_fallback="tadpole", is_starter=False,
    ),
    "thunder_toad": Species(
        id="thunder_toad", display_name="Thunder Toad", kind="amphibian",
        base_hp=46, base_atk=36, base_def=29, base_spd=22, base_luck=17,
        blurb="Skin crackling with stored storm. Its croak carries a mile.",
        sprite_fallback="tadpole", is_starter=False,
    ),
    "basalt_toad": Species(
        id="basalt_toad", display_name="Basalt Toad", kind="amphibian",
        base_hp=52, base_atk=28, base_def=38, base_spd=15, base_luck=16,
        blurb="A toad carved out of cooled lava. Shrugs off blows and weathers.",
        sprite_fallback="tadpole", is_starter=False,
    ),

    # ─── hatchling_turtle lineage (depth 7, tier-3 crocodile branch + tier-7 apex branch) ─
    "baby_crocodile": Species(
        id="baby_crocodile", display_name="Baby Crocodile", kind="reptile",
        base_hp=22, base_atk=14, base_def=15, base_spd=9, base_luck=9,
        blurb="A palm-sized ambush predator. Already knows how to wait.",
        evolutions=(Evolution("nile_croc", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="hatchling_turtle", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "nile_croc": Species(
        id="nile_croc", display_name="Nile Crocodile", kind="reptile",
        base_hp=28, base_atk=20, base_def=19, base_spd=11, base_luck=10,
        blurb="Four meters of ambush and bite. Doesn't miss its first lunge.",
        evolutions=(
            Evolution("saltwater_apex", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("armored_caiman", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="hatchling_turtle", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "saltwater_apex": Species(
        id="saltwater_apex", display_name="Saltwater Apex", kind="reptile",
        base_hp=36, base_atk=32, base_def=22, base_spd=22, base_luck=12,
        blurb="The biggest reptile alive. Runs down anything near the tideline.",
        sprite_fallback="hatchling_turtle", is_starter=False,
    ),
    "armored_caiman": Species(
        id="armored_caiman", display_name="Armored Caiman", kind="reptile",
        base_hp=42, base_atk=22, base_def=32, base_spd=14, base_luck=12,
        blurb="Bone-plated from snout to tail. A pond-bottom fortress.",
        sprite_fallback="hatchling_turtle", is_starter=False,
    ),
    "titan_reef_turtle": Species(
        id="titan_reef_turtle", display_name="Titan Reef Turtle", kind="reptile",
        base_hp=50, base_atk=32, base_def=34, base_spd=24, base_luck=15,
        blurb="A six-meter ocean-wanderer. Breaches like a whale in slow motion.",
        sprite_fallback="hatchling_turtle", is_starter=False,
    ),
    "fortress_shell": Species(
        id="fortress_shell", display_name="Fortress Shell", kind="reptile",
        base_hp=58, base_atk=24, base_def=44, base_spd=10, base_luck=14,
        blurb="Shell plates as thick as a car door. Indifferent to cannon fire.",
        sprite_fallback="hatchling_turtle", is_starter=False,
    ),

    # ─── minnow lineage (depth 7, tier-3 shark branch + tier-7 apex branch) ─
    "reef_shark": Species(
        id="reef_shark", display_name="Reef Shark", kind="aquatic",
        base_hp=22, base_atk=15, base_def=12, base_spd=18, base_luck=10,
        blurb="A sleek coral-zone cruiser. Always first at the feed.",
        evolutions=(Evolution("tiger_shark", requirements={"spd": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="minnow", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "tiger_shark": Species(
        id="tiger_shark", display_name="Tiger Shark", kind="aquatic",
        base_hp=26, base_atk=20, base_def=14, base_spd=21, base_luck=11,
        blurb="An omnivorous hunter that swallows shipwrecks whole.",
        evolutions=(
            Evolution("siren_shark", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("fortress_shark", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="minnow", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "siren_shark": Species(
        id="siren_shark", display_name="Siren Shark", kind="aquatic",
        base_hp=32, base_atk=30, base_def=16, base_spd=28, base_luck=13,
        blurb="A pelagic blur. Hits too fast for prey to register.",
        sprite_fallback="minnow", is_starter=False,
    ),
    "fortress_shark": Species(
        id="fortress_shark", display_name="Fortress Shark", kind="aquatic",
        base_hp=40, base_atk=20, base_def=28, base_spd=18, base_luck=12,
        blurb="A blunt-nosed tank with a sandpaper hide. Nothing gets a grip.",
        sprite_fallback="minnow", is_starter=False,
    ),
    "apex_kraken_fish": Species(
        id="apex_kraken_fish", display_name="Apex Kraken Fish", kind="aquatic",
        base_hp=48, base_atk=40, base_def=28, base_spd=32, base_luck=16,
        blurb="A myth that turned out to be real. Drags ships down and then the stories.",
        sprite_fallback="minnow", is_starter=False,
    ),
    "armored_leviathan": Species(
        id="armored_leviathan", display_name="Armored Leviathan", kind="aquatic",
        base_hp=56, base_atk=30, base_def=38, base_spd=22, base_luck=15,
        blurb="Hull-plated whale-fish. A reef that decided to swim.",
        sprite_fallback="minnow", is_starter=False,
    ),

    # ─── wren lineage (depth 7, tier-3 owl branch + tier-7 apex branch) ────
    "barn_owl": Species(
        id="barn_owl", display_name="Barn Owl", kind="avian",
        base_hp=20, base_atk=13, base_def=10, base_spd=17, base_luck=13,
        blurb="A silent heart-faced hunter. Hears a mouse breathe.",
        evolutions=(Evolution("horned_owl", requirements={"spd": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="wren", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "horned_owl": Species(
        id="horned_owl", display_name="Great Horned Owl", kind="avian",
        base_hp=24, base_atk=17, base_def=12, base_spd=19, base_luck=14,
        blurb="The tiger of the owl world. Takes skunks without hesitating.",
        evolutions=(
            Evolution("ghost_owl", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("stone_owl", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="wren", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "ghost_owl": Species(
        id="ghost_owl", display_name="Ghost Owl", kind="avian",
        base_hp=30, base_atk=26, base_def=13, base_spd=28, base_luck=16,
        blurb="A white-winged twilight killer. Hangs in the air, then is suddenly not.",
        sprite_fallback="wren", is_starter=False,
    ),
    "stone_owl": Species(
        id="stone_owl", display_name="Stone Owl", kind="avian",
        base_hp=38, base_atk=17, base_def=26, base_spd=14, base_luck=15,
        blurb="A monolithic perched owl carved from river rock. Blinks once a year.",
        sprite_fallback="wren", is_starter=False,
    ),
    "thunder_eagle": Species(
        id="thunder_eagle", display_name="Thunder Eagle", kind="avian",
        base_hp=44, base_atk=42, base_def=22, base_spd=34, base_luck=18,
        blurb="Storm-riding apex. Claws crackle with static before the strike.",
        sprite_fallback="wren", is_starter=False,
    ),
    "shadow_eagle": Species(
        id="shadow_eagle", display_name="Shadow Eagle", kind="avian",
        base_hp=50, base_atk=32, base_def=30, base_spd=22, base_luck=17,
        blurb="A shade-cloaked giant. Watches from the high stones before it moves.",
        sprite_fallback="wren", is_starter=False,
    ),

    # ═════════════════════════════════════════════════════════════════════
    # Split-and-converge — batch 2: beasts (field_mouse, squirrel, hedgehog)
    # ═════════════════════════════════════════════════════════════════════

    # ─── field_mouse lineage (depth 7) ────────────────────────────────────
    "shrew_hunter": Species(
        id="shrew_hunter", display_name="Shrew Hunter", kind="beast",
        base_hp=22, base_atk=11, base_def=15, base_spd=12, base_luck=10,
        blurb="A tiny insectivore with a venomous bite and a relentless appetite.",
        evolutions=(Evolution("mole_lord", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="field_mouse", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "mole_lord": Species(
        id="mole_lord", display_name="Mole Lord", kind="beast",
        base_hp=28, base_atk=14, base_def=20, base_spd=10, base_luck=11,
        blurb="A subterranean ruler that never needs to see daylight.",
        evolutions=(
            Evolution("alpine_colossus", requirements={"int_": 62, "luck": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("glacier_rat", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="field_mouse", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "glacier_rat": Species(
        id="glacier_rat", display_name="Glacier Rat", kind="beast",
        base_hp=40, base_atk=18, base_def=30, base_spd=12, base_luck=13,
        blurb="A white-furred tundra burrower. Its bones are said to conduct cold.",
        sprite_fallback="field_mouse", is_starter=False,
    ),
    "titan_rat_king": Species(
        id="titan_rat_king", display_name="Titan Rat King", kind="beast",
        base_hp=48, base_atk=32, base_def=26, base_spd=26, base_luck=18,
        blurb="A prehistoric tyrant-rodent. Leads a horde at full sprint.",
        sprite_fallback="field_mouse", is_starter=False,
    ),
    "burrow_emperor": Species(
        id="burrow_emperor", display_name="Burrow Emperor", kind="beast",
        base_hp=56, base_atk=22, base_def=40, base_spd=14, base_luck=16,
        blurb="Ruler of a mile-wide underground city. Unmoved by surface happenings.",
        sprite_fallback="field_mouse", is_starter=False,
    ),

    # ─── squirrel lineage (depth 5) — shares alpine_colossus with field_mouse ─
    "red_fox_kit": Species(
        id="red_fox_kit", display_name="Red Fox Kit", kind="beast",
        base_hp=20, base_atk=11, base_def=12, base_spd=14, base_luck=13,
        blurb="A pointy-eared opportunist. Learned every trick the forest knows.",
        evolutions=(Evolution("silver_fox", requirements={"spd": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="squirrel", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "silver_fox": Species(
        id="silver_fox", display_name="Silver Fox", kind="beast",
        base_hp=24, base_atk=15, base_def=14, base_spd=17, base_luck=15,
        blurb="A moonlit hunter with a brush for a tail and an answer for every trap.",
        evolutions=(
            Evolution("alpine_colossus", requirements={"int_": 62, "luck": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("shadow_fox", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="squirrel", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "shadow_fox": Species(
        id="shadow_fox", display_name="Shadow Fox", kind="beast",
        base_hp=34, base_atk=20, base_def=28, base_spd=16, base_luck=16,
        blurb="A smoke-cloaked trickster. Steps leave no sound and no mark.",
        sprite_fallback="squirrel", is_starter=False,
    ),
    "cloud_squirrel": Species(
        id="cloud_squirrel", display_name="Cloud Squirrel", kind="beast",
        base_hp=34, base_atk=24, base_def=16, base_spd=28, base_luck=15,
        blurb="A high-canopy glider that clears canyons in a single leap.",
        sprite_fallback="squirrel", is_starter=False,
    ),
    "ironclad_squirrel": Species(
        id="ironclad_squirrel", display_name="Ironclad Squirrel", kind="beast",
        base_hp=40, base_atk=16, base_def=30, base_spd=14, base_luck=16,
        blurb="Its tail is a shield, its acorns are weapons, and its stash is fortified.",
        sprite_fallback="squirrel", is_starter=False,
    ),

    # ─── alpine_colossus: SHARED apex (field_mouse + squirrel converge here) ─
    "alpine_colossus": Species(
        id="alpine_colossus", display_name="Alpine Colossus", kind="beast",
        base_hp=44, base_atk=28, base_def=22, base_spd=24, base_luck=15,
        blurb="A hulking mountain runner. The elder of any peak it calls home. "
              "Both mouse-line and squirrel-line buddies can converge here.",
        sprite_fallback="field_mouse", is_starter=False,
    ),

    # ─── hedgehog lineage (depth 7) ───────────────────────────────────────
    "mountain_mole": Species(
        id="mountain_mole", display_name="Mountain Mole", kind="beast",
        base_hp=24, base_atk=9, base_def=18, base_spd=8, base_luck=10,
        blurb="A boulder-dwelling digger. Sharper hearing than sight, which is saying something.",
        evolutions=(Evolution("cave_mole", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="hedgehog", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "cave_mole": Species(
        id="cave_mole", display_name="Cave Mole", kind="beast",
        base_hp=30, base_atk=12, base_def=24, base_spd=9, base_luck=11,
        blurb="A blind stonework specialist. Lives in caverns no one else has seen.",
        evolutions=(
            Evolution("iron_mole", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("obsidian_mole", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="hedgehog", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "iron_mole": Species(
        id="iron_mole", display_name="Iron Mole", kind="beast",
        base_hp=36, base_atk=22, base_def=28, base_spd=14, base_luck=13,
        blurb="A metal-clawed tunneler. Digs through solid rock in a straight line.",
        sprite_fallback="hedgehog", is_starter=False,
    ),
    "obsidian_mole": Species(
        id="obsidian_mole", display_name="Obsidian Mole", kind="beast",
        base_hp=44, base_atk=14, base_def=36, base_spd=8, base_luck=14,
        blurb="A glass-plated burrower. Coals inside, volcanic outside.",
        sprite_fallback="hedgehog", is_starter=False,
    ),
    "thunder_sloth": Species(
        id="thunder_sloth", display_name="Thunder Sloth", kind="beast",
        base_hp=52, base_atk=46, base_def=34, base_spd=26, base_luck=18,
        blurb="An Ice Age colossus with claws like thunderheads. Charges surprisingly fast for a sloth.",
        sprite_fallback="hedgehog", is_starter=False,
    ),
    "bedrock_sloth": Species(
        id="bedrock_sloth", display_name="Bedrock Sloth", kind="beast",
        base_hp=60, base_atk=28, base_def=50, base_spd=10, base_luck=17,
        blurb="A mountain-shouldered tank. Roots into the ground and doesn't move for seasons.",
        sprite_fallback="hedgehog", is_starter=False,
    ),

    # ═════════════════════════════════════════════════════════════════════
    # Split-and-converge — batch 3: insects (bee, ladybug, caterpillar)
    # Shared apex: titan_wing_beetle (ladybug + caterpillar converge)
    # ═════════════════════════════════════════════════════════════════════

    # ─── bee lineage (depth 5, no cross-lineage merge) ────────────────────
    "moth_wasp": Species(
        id="moth_wasp", display_name="Moth-Wing Wasp", kind="insect",
        base_hp=12, base_atk=14, base_def=10, base_spd=14, base_luck=10,
        blurb="A fuzzy-winged hybrid. Half pollinator, half assassin.",
        evolutions=(Evolution("silk_wasp", requirements={"atk": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="bee", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "silk_wasp": Species(
        id="silk_wasp", display_name="Silk Wasp", kind="insect",
        base_hp=14, base_atk=16, base_def=12, base_spd=16, base_luck=11,
        blurb="Spins webs thin enough to catch starlight.",
        evolutions=(
            Evolution("mirror_wasp", requirements={"int_": 62, "luck": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("silk_queen", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="bee", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "mirror_wasp": Species(
        id="mirror_wasp", display_name="Mirror Wasp", kind="insect",
        base_hp=18, base_atk=20, base_def=14, base_spd=22, base_luck=18,
        blurb="Wings like polished obsidian. Every strike reflects its foe's mistake.",
        sprite_fallback="bee", is_starter=False,
    ),
    "silk_queen": Species(
        id="silk_queen", display_name="Silk Queen", kind="insect",
        base_hp=22, base_atk=16, base_def=26, base_spd=14, base_luck=16,
        blurb="A matriarch at the center of a glass-silk fortress.",
        sprite_fallback="bee", is_starter=False,
    ),
    "venom_general": Species(
        id="venom_general", display_name="Venom General", kind="insect",
        base_hp=26, base_atk=34, base_def=14, base_spd=28, base_luck=12,
        blurb="A wasp-lord whose single sting fells giants.",
        sprite_fallback="bee", is_starter=False,
    ),
    "carapace_scout": Species(
        id="carapace_scout", display_name="Carapace Scout", kind="insect",
        base_hp=32, base_atk=22, base_def=26, base_spd=20, base_luck=12,
        blurb="An armored recon ant-wasp. Watches, reports, then vanishes.",
        sprite_fallback="bee", is_starter=False,
    ),

    # ─── ladybug lineage (depth 7) — shares titan_wing_beetle with caterpillar ─
    "glow_bug": Species(
        id="glow_bug", display_name="Glow Bug", kind="insect",
        base_hp=22, base_atk=10, base_def=14, base_spd=8, base_luck=14,
        blurb="A beetle that carries its own lantern. Blinks in code.",
        evolutions=(Evolution("ember_beetle", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="ladybug", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "ember_beetle": Species(
        id="ember_beetle", display_name="Ember Beetle", kind="insect",
        base_hp=26, base_atk=13, base_def=18, base_spd=9, base_luck=15,
        blurb="Carries live coals in its carapace. Glows through armor plates.",
        evolutions=(
            Evolution("titan_wing_beetle", requirements={"int_": 62, "luck": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("cinder_beetle", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="ladybug", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "cinder_beetle": Species(
        id="cinder_beetle", display_name="Cinder Beetle", kind="insect",
        base_hp=34, base_atk=16, base_def=28, base_spd=8, base_luck=16,
        blurb="Slag-hard plates. Cools to black between strikes.",
        sprite_fallback="ladybug", is_starter=False,
    ),
    "storm_scorpion": Species(
        id="storm_scorpion", display_name="Storm Scorpion", kind="insect",
        base_hp=46, base_atk=40, base_def=30, base_spd=22, base_luck=18,
        blurb="Claws like lightning rods. The sky answers when it walks.",
        sprite_fallback="ladybug", is_starter=False,
    ),
    "obelisk_scorpion": Species(
        id="obelisk_scorpion", display_name="Obelisk Scorpion", kind="insect",
        base_hp=54, base_atk=30, base_def=42, base_spd=14, base_luck=17,
        blurb="Carved of living stone. Older than the rivers around it.",
        sprite_fallback="ladybug", is_starter=False,
    ),

    # ─── titan_wing_beetle: SHARED apex (ladybug + caterpillar converge here) ─
    "titan_wing_beetle": Species(
        id="titan_wing_beetle", display_name="Titan Wing Beetle", kind="insect",
        base_hp=40, base_atk=22, base_def=20, base_spd=26, base_luck=20,
        blurb="A hand-sized iridescent flyer. Shared apex for the ladybug and caterpillar lines.",
        sprite_fallback="ladybug", is_starter=False,
    ),

    # ─── caterpillar lineage (depth 7) — shares titan_wing_beetle with ladybug ─
    "stick_bug": Species(
        id="stick_bug", display_name="Stick Bug", kind="insect",
        base_hp=24, base_atk=8, base_def=16, base_spd=10, base_luck=12,
        blurb="A twig you definitely don't notice — until it moves.",
        evolutions=(Evolution("walking_branch", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="caterpillar", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "walking_branch": Species(
        id="walking_branch", display_name="Walking Branch", kind="insect",
        base_hp=28, base_atk=11, base_def=20, base_spd=11, base_luck=13,
        blurb="A meter-long camouflaged insect. Pretends to be a tree and mostly succeeds.",
        evolutions=(
            Evolution("titan_wing_beetle", requirements={"int_": 62, "luck": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("moss_giant", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="caterpillar", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "moss_giant": Species(
        id="moss_giant", display_name="Moss Giant", kind="insect",
        base_hp=36, base_atk=12, base_def=28, base_spd=9, base_luck=15,
        blurb="A walking moss-covered boulder. Lichen grows faster than it moves, and that's saying something.",
        sprite_fallback="caterpillar", is_starter=False,
    ),
    "thunder_dragonfly": Species(
        id="thunder_dragonfly", display_name="Thunder Dragonfly", kind="insect",
        base_hp=44, base_atk=34, base_def=22, base_spd=40, base_luck=19,
        blurb="A storm-born insect apex. Wings carve the sky into noise.",
        sprite_fallback="caterpillar", is_starter=False,
    ),
    "fossil_dragonfly": Species(
        id="fossil_dragonfly", display_name="Fossil Dragonfly", kind="insect",
        base_hp=52, base_atk=22, base_def=36, base_spd=22, base_luck=18,
        blurb="Petrified wings that somehow still beat. Older than most mountains.",
        sprite_fallback="caterpillar", is_starter=False,
    ),

    # ═════════════════════════════════════════════════════════════════════
    # Split-and-converge — batch 4: amphibians (froglet, newt, axolotl)
    # Shared apex: elder_salamander (newt + axolotl converge)
    # ═════════════════════════════════════════════════════════════════════

    # ─── froglet lineage (depth 5, no cross-lineage merge) ────────────────
    "clawed_frog": Species(
        id="clawed_frog", display_name="Clawed Frog", kind="amphibian",
        base_hp=22, base_atk=10, base_def=14, base_spd=12, base_luck=11,
        blurb="Scythe-toed amphibian that hunts by pinning its prey.",
        evolutions=(Evolution("amazon_toad", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="froglet", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "amazon_toad": Species(
        id="amazon_toad", display_name="Amazon Toad", kind="amphibian",
        base_hp=26, base_atk=12, base_def=17, base_spd=13, base_luck=12,
        blurb="Jungle-canopy ruler with a pocket of tadpoles on its back.",
        evolutions=(
            Evolution("jungle_king", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("vine_terror", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="froglet", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "jungle_king": Species(
        id="jungle_king", display_name="Jungle King Frog", kind="amphibian",
        base_hp=32, base_atk=22, base_def=16, base_spd=24, base_luck=14,
        blurb="A crowned canopy ambusher. One leap crosses a clearing.",
        sprite_fallback="froglet", is_starter=False,
    ),
    "vine_terror": Species(
        id="vine_terror", display_name="Vine Terror", kind="amphibian",
        base_hp=38, base_atk=14, base_def=28, base_spd=12, base_luck=15,
        blurb="A bramble-armored toad. Moves with the forest floor.",
        sprite_fallback="froglet", is_starter=False,
    ),
    "sky_toad": Species(
        id="sky_toad", display_name="Sky Toad", kind="amphibian",
        base_hp=34, base_atk=28, base_def=18, base_spd=26, base_luck=16,
        blurb="A gliding toad with cloud-membranes between its toes.",
        sprite_fallback="froglet", is_starter=False,
    ),
    "stone_toad": Species(
        id="stone_toad", display_name="Stone Toad", kind="amphibian",
        base_hp=42, base_atk=20, base_def=32, base_spd=10, base_luck=15,
        blurb="A weathered boulder toad. Sits still for a thousand years between meals.",
        sprite_fallback="froglet", is_starter=False,
    ),

    # ─── newt lineage (depth 5) — shares elder_salamander with axolotl ────
    "cave_salamander": Species(
        id="cave_salamander", display_name="Cave Salamander", kind="amphibian",
        base_hp=22, base_atk=8, base_def=16, base_spd=10, base_luck=13,
        blurb="A pale-skinned cavern dweller. Never sees light and needs none.",
        evolutions=(Evolution("blind_salamander", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="newt", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "blind_salamander": Species(
        id="blind_salamander", display_name="Blind Salamander", kind="amphibian",
        base_hp=26, base_atk=10, base_def=20, base_spd=10, base_luck=14,
        blurb="A pearl-white hunter with lightless eyes. Feels the ripple of footsteps in still water.",
        evolutions=(
            Evolution("elder_salamander", requirements={"int_": 62, "luck": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("dream_salamander", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="newt", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "dream_salamander": Species(
        id="dream_salamander", display_name="Dream Salamander", kind="amphibian",
        base_hp=34, base_atk=12, base_def=26, base_spd=11, base_luck=16,
        blurb="A drowsing oracle. Its skin shifts color with forgotten memories.",
        sprite_fallback="newt", is_starter=False,
    ),
    "river_king_salamander": Species(
        id="river_king_salamander", display_name="River King Salamander", kind="amphibian",
        base_hp=40, base_atk=26, base_def=24, base_spd=22, base_luck=16,
        blurb="A crowned river-bottom apex. Its back is a territorial boundary.",
        sprite_fallback="newt", is_starter=False,
    ),
    "mountain_salamander": Species(
        id="mountain_salamander", display_name="Mountain Salamander", kind="amphibian",
        base_hp=48, base_atk=18, base_def=36, base_spd=10, base_luck=15,
        blurb="A granite-skinned giant. Lives in cold mountain springs for centuries.",
        sprite_fallback="newt", is_starter=False,
    ),

    # ─── elder_salamander: SHARED apex (newt + axolotl converge here) ────
    "elder_salamander": Species(
        id="elder_salamander", display_name="Elder Salamander", kind="amphibian",
        base_hp=44, base_atk=20, base_def=26, base_spd=16, base_luck=22,
        blurb="A pale, ancient amphibian said to whisper advice to rivers. Shared apex for newt and axolotl lines.",
        sprite_fallback="newt", is_starter=False,
    ),

    # ─── axolotl lineage (depth 5) — shares elder_salamander with newt ────
    "pond_wyrm": Species(
        id="pond_wyrm", display_name="Pond Wyrm", kind="amphibian",
        base_hp=24, base_atk=10, base_def=15, base_spd=11, base_luck=13,
        blurb="A finned pond-bottom prowler. Looks harmless until the last second.",
        evolutions=(Evolution("lake_wyrm", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="axolotl", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "lake_wyrm": Species(
        id="lake_wyrm", display_name="Lake Wyrm", kind="amphibian",
        base_hp=28, base_atk=13, base_def=19, base_spd=12, base_luck=14,
        blurb="A six-foot lake predator with gills like fans and gills like knives.",
        evolutions=(
            Evolution("elder_salamander", requirements={"int_": 62, "luck": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("crystal_wyrm", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="axolotl", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "crystal_wyrm": Species(
        id="crystal_wyrm", display_name="Crystal Wyrm", kind="amphibian",
        base_hp=36, base_atk=14, base_def=28, base_spd=12, base_luck=17,
        blurb="A wyrm with a body like polished quartz. Each scale catches a different color.",
        sprite_fallback="axolotl", is_starter=False,
    ),
    "thunder_axolotl": Species(
        id="thunder_axolotl", display_name="Thunder Axolotl", kind="amphibian",
        base_hp=42, base_atk=28, base_def=22, base_spd=24, base_luck=17,
        blurb="Gills spark with stored lightning. A storm's apex pond-dweller.",
        sprite_fallback="axolotl", is_starter=False,
    ),
    "stone_axolotl": Species(
        id="stone_axolotl", display_name="Stone Axolotl", kind="amphibian",
        base_hp=50, base_atk=20, base_def=36, base_spd=12, base_luck=16,
        blurb="A petrified axolotl so old its smile became geology.",
        sprite_fallback="axolotl", is_starter=False,
    ),

    # ═════════════════════════════════════════════════════════════════════
    # Split-and-converge — batch 5: aquatics (guppy, snail, shrimp)
    # Shared apex: deep_crustacean (snail + shrimp converge)
    # ═════════════════════════════════════════════════════════════════════

    # ─── guppy lineage (depth 7, no cross-lineage merge) ──────────────────
    "pufferfish": Species(
        id="pufferfish", display_name="Pufferfish", kind="aquatic",
        base_hp=20, base_atk=10, base_def=16, base_spd=9, base_luck=12,
        blurb="A balloon with opinions. Inflates into a spiky deterrent.",
        evolutions=(Evolution("spiny_puffer", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="guppy", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "spiny_puffer": Species(
        id="spiny_puffer", display_name="Spiny Puffer", kind="aquatic",
        base_hp=24, base_atk=12, base_def=20, base_spd=9, base_luck=13,
        blurb="Longer spines, shorter temper. A reef's floating mine.",
        evolutions=(
            Evolution("thunder_puffer", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS, grants_skill="battle_cry"),
            Evolution("iron_puffer", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS, grants_skill="iron_skin"),
        ),
        sprite_fallback="guppy", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "thunder_puffer": Species(
        id="thunder_puffer", display_name="Thunder Puffer", kind="aquatic",
        base_hp=32, base_atk=24, base_def=20, base_spd=22, base_luck=15,
        blurb="A storm-charged blowfish. Its spines crackle before they strike.",
        sprite_fallback="guppy", is_starter=False,
    ),
    "iron_puffer": Species(
        id="iron_puffer", display_name="Iron Puffer", kind="aquatic",
        base_hp=40, base_atk=14, base_def=32, base_spd=8, base_luck=14,
        blurb="Inflates into a sphere of living iron. A reef's immovable gate.",
        sprite_fallback="guppy", is_starter=False,
    ),
    "storm_megalodon": Species(
        id="storm_megalodon", display_name="Storm Megalodon", kind="aquatic",
        base_hp=60, base_atk=46, base_def=28, base_spd=38, base_luck=22,
        blurb="A 60-foot shark that rides hurricanes like currents.",
        sprite_fallback="guppy", is_starter=False,
    ),
    "basalt_megalodon": Species(
        id="basalt_megalodon", display_name="Basalt Megalodon", kind="aquatic",
        base_hp=72, base_atk=34, base_def=48, base_spd=22, base_luck=20,
        blurb="A trench-depth shark with hide like cooled lava. Nothing hurts it.",
        sprite_fallback="guppy", is_starter=False,
    ),

    # ─── snail lineage (depth 7) — shares deep_crustacean with shrimp ─────
    "hermit_crab": Species(
        id="hermit_crab", display_name="Hermit Crab", kind="aquatic",
        base_hp=24, base_atk=8, base_def=20, base_spd=7, base_luck=12,
        blurb="A soft-bodied borrower of other creatures' shells.",
        evolutions=(Evolution("coconut_claw", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="snail", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "coconut_claw": Species(
        id="coconut_claw", display_name="Coconut Claw", kind="aquatic",
        base_hp=30, base_atk=14, base_def=24, base_spd=8, base_luck=13,
        blurb="A land-walking crab that cracks coconuts with one pinch.",
        evolutions=(
            Evolution("deep_crustacean", requirements={"int_": 62, "luck": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("hermit_king", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="snail", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "hermit_king": Species(
        id="hermit_king", display_name="Hermit King", kind="aquatic",
        base_hp=44, base_atk=18, base_def=36, base_spd=8, base_luck=15,
        blurb="A throned crab wearing a shell as large as a boulder.",
        sprite_fallback="snail", is_starter=False,
    ),
    "thunder_squid": Species(
        id="thunder_squid", display_name="Thunder Squid", kind="aquatic",
        base_hp=52, base_atk=36, base_def=26, base_spd=38, base_luck=20,
        blurb="Tentacles trailing a static wake. Fires bolts through the black water.",
        sprite_fallback="snail", is_starter=False,
    ),
    "abyss_squid": Species(
        id="abyss_squid", display_name="Abyss Squid", kind="aquatic",
        base_hp=68, base_atk=26, base_def=44, base_spd=22, base_luck=20,
        blurb="A trench-dwelling colossus. Ink clouds swallow light whole.",
        sprite_fallback="snail", is_starter=False,
    ),

    # ─── deep_crustacean: SHARED apex (snail + shrimp converge here) ──────
    "deep_crustacean": Species(
        id="deep_crustacean", display_name="Deep Crustacean", kind="aquatic",
        base_hp=46, base_atk=22, base_def=28, base_spd=14, base_luck=24,
        blurb="An abyssal scavenger-sage. Shell bioluminescent with forgotten constellations. Shared apex for snail and shrimp lines.",
        sprite_fallback="snail", is_starter=False,
    ),

    # ─── shrimp lineage (depth 7) — shares deep_crustacean with snail ─────
    "pistol_shrimp": Species(
        id="pistol_shrimp", display_name="Pistol Shrimp", kind="aquatic",
        base_hp=22, base_atk=13, base_def=17, base_spd=13, base_luck=12,
        blurb="Snaps its claw to shoot a cavitation bullet. Louder than a gunshot.",
        evolutions=(Evolution("mantis_titan", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="shrimp", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "mantis_titan": Species(
        id="mantis_titan", display_name="Mantis Titan", kind="aquatic",
        base_hp=28, base_atk=17, base_def=22, base_spd=15, base_luck=13,
        blurb="A meter-long mantis shrimp. Sees colors beyond light itself.",
        evolutions=(
            Evolution("deep_crustacean", requirements={"int_": 62, "luck": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("sonar_titan", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="shrimp", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "sonar_titan": Species(
        id="sonar_titan", display_name="Sonar Titan", kind="aquatic",
        base_hp=42, base_atk=18, base_def=34, base_spd=14, base_luck=16,
        blurb="A reef-sized crustacean that navigates by bouncing thunderclaps.",
        sprite_fallback="shrimp", is_starter=False,
    ),
    "storm_euryp": Species(
        id="storm_euryp", display_name="Storm Eurypterid", kind="aquatic",
        base_hp=54, base_atk=38, base_def=26, base_spd=36, base_luck=19,
        blurb="A prehistoric sea scorpion reborn in the tempest. Tail lightning in a spiral.",
        sprite_fallback="shrimp", is_starter=False,
    ),
    "cavern_euryp": Species(
        id="cavern_euryp", display_name="Cavern Eurypterid", kind="aquatic",
        base_hp=66, base_atk=26, base_def=46, base_spd=18, base_luck=18,
        blurb="A cave-system sea scorpion the size of a horse. Walls don't stop it.",
        sprite_fallback="shrimp", is_starter=False,
    ),

    # ═════════════════════════════════════════════════════════════════════
    # Split-and-converge — batch 6: reptiles (baby_gecko, anole, skink)
    # Shared apex: monitor_titan (anole + skink converge)
    # ═════════════════════════════════════════════════════════════════════

    # ─── baby_gecko lineage (depth 5, no cross-lineage merge) ─────────────
    "skink_cousin": Species(
        id="skink_cousin", display_name="Dwarf Skink", kind="reptile",
        base_hp=20, base_atk=9, base_def=15, base_spd=12, base_luck=12,
        blurb="A small, smooth-scaled cousin to the geckos. Burrows fast.",
        evolutions=(Evolution("glass_lizard", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="baby_gecko", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "glass_lizard": Species(
        id="glass_lizard", display_name="Glass Lizard", kind="reptile",
        base_hp=24, base_atk=11, base_def=19, base_spd=13, base_luck=13,
        blurb="A legless lizard that drops its tail like shattering glass.",
        evolutions=(
            Evolution("thunder_lizard", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("crystal_gecko", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="baby_gecko", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "thunder_lizard": Species(
        id="thunder_lizard", display_name="Thunder Lizard", kind="reptile",
        base_hp=32, base_atk=24, base_def=18, base_spd=26, base_luck=15,
        blurb="A swift reptile crackling with storm static. Named by ancient herders.",
        sprite_fallback="baby_gecko", is_starter=False,
    ),
    "crystal_gecko": Species(
        id="crystal_gecko", display_name="Crystal Gecko", kind="reptile",
        base_hp=40, base_atk=14, base_def=32, base_spd=10, base_luck=16,
        blurb="Translucent scales harder than quartz. A living cathedral window.",
        sprite_fallback="baby_gecko", is_starter=False,
    ),
    "canopy_gecko_king": Species(
        id="canopy_gecko_king", display_name="Canopy Gecko King", kind="reptile",
        base_hp=36, base_atk=28, base_def=20, base_spd=30, base_luck=18,
        blurb="A crowned giant gecko that rules a single tree absolutely.",
        sprite_fallback="baby_gecko", is_starter=False,
    ),
    "stone_gecko_elder": Species(
        id="stone_gecko_elder", display_name="Stone Gecko Elder", kind="reptile",
        base_hp=46, base_atk=18, base_def=38, base_spd=14, base_luck=17,
        blurb="A basalt-skinned patriarch. Its toe-pads grip cliffs and centuries alike.",
        sprite_fallback="baby_gecko", is_starter=False,
    ),

    # ─── anole lineage (depth 5) — shares monitor_titan with skink ────────
    "small_varanid": Species(
        id="small_varanid", display_name="Small Varanid", kind="reptile",
        base_hp=22, base_atk=10, base_def=16, base_spd=13, base_luck=12,
        blurb="A palm-sized monitor lizard. Hunts like its giant cousins in miniature.",
        evolutions=(Evolution("tree_monitor", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="anole", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "tree_monitor": Species(
        id="tree_monitor", display_name="Tree Monitor", kind="reptile",
        base_hp=26, base_atk=13, base_def=20, base_spd=15, base_luck=13,
        blurb="An arboreal monitor with whip-tail and emerald scales.",
        evolutions=(
            Evolution("monitor_titan", requirements={"int_": 62, "luck": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("canopy_stalker", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="anole", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "canopy_stalker": Species(
        id="canopy_stalker", display_name="Canopy Stalker", kind="reptile",
        base_hp=40, base_atk=14, base_def=32, base_spd=12, base_luck=16,
        blurb="A silent, plated monitor that hunts by patience alone.",
        sprite_fallback="anole", is_starter=False,
    ),
    "mirage_chameleon": Species(
        id="mirage_chameleon", display_name="Mirage Chameleon", kind="reptile",
        base_hp=36, base_atk=28, base_def=20, base_spd=30, base_luck=18,
        blurb="Bends light so perfectly it appears in two places at once.",
        sprite_fallback="anole", is_starter=False,
    ),
    "fortress_chameleon": Species(
        id="fortress_chameleon", display_name="Fortress Chameleon", kind="reptile",
        base_hp=48, base_atk=18, base_def=38, base_spd=14, base_luck=16,
        blurb="A bunker of layered scales. Moves only when it wants to.",
        sprite_fallback="anole", is_starter=False,
    ),

    # ─── monitor_titan: SHARED apex (anole + skink converge here) ─────────
    "monitor_titan": Species(
        id="monitor_titan", display_name="Monitor Titan", kind="reptile",
        base_hp=44, base_atk=22, base_def=26, base_spd=18, base_luck=24,
        blurb="A house-sized varanid that reads the wind. Shared apex for anole and skink lines.",
        sprite_fallback="anole", is_starter=False,
    ),

    # ─── skink lineage (depth 7) — shares monitor_titan with anole ────────
    "fat_tail_lizard": Species(
        id="fat_tail_lizard", display_name="Fat-Tail Lizard", kind="reptile",
        base_hp=24, base_atk=10, base_def=18, base_spd=11, base_luck=11,
        blurb="Stores fat in its stubby tail. Desert-tough, unshakable.",
        evolutions=(Evolution("perentie", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="skink", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "perentie": Species(
        id="perentie", display_name="Perentie", kind="reptile",
        base_hp=30, base_atk=15, base_def=22, base_spd=12, base_luck=12,
        blurb="Australia's largest monitor. Sprints into dens to drag out prey.",
        evolutions=(
            Evolution("monitor_titan", requirements={"int_": 62, "luck": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("sand_prowler", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="skink", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "sand_prowler": Species(
        id="sand_prowler", display_name="Sand Prowler", kind="reptile",
        base_hp=44, base_atk=16, base_def=34, base_spd=14, base_luck=14,
        blurb="A dune-colored monitor that surfaces only to eat.",
        sprite_fallback="skink", is_starter=False,
    ),
    "thunder_mosasaur": Species(
        id="thunder_mosasaur", display_name="Thunder Mosasaur", kind="reptile",
        base_hp=58, base_atk=44, base_def=26, base_spd=40, base_luck=22,
        blurb="A stormbound marine reptile. Breaches like a falling mountain.",
        sprite_fallback="skink", is_starter=False,
    ),
    "bedrock_pliosaur": Species(
        id="bedrock_pliosaur", display_name="Bedrock Pliosaur", kind="reptile",
        base_hp=72, base_atk=30, base_def=48, base_spd=18, base_luck=20,
        blurb="A trench-dwelling pliosaur with hide like tectonic plate.",
        sprite_fallback="skink", is_starter=False,
    ),

    # ═════════════════════════════════════════════════════════════════════
    # Split-and-converge — batch 7: avians (sparrow, chick, duckling)
    # Shared apex: ground_titan_bird (sparrow + chick converge)
    # ═════════════════════════════════════════════════════════════════════

    # ─── sparrow lineage (depth 7) — shares ground_titan_bird with chick ──
    "pigeon": Species(
        id="pigeon", display_name="Pigeon", kind="avian",
        base_hp=20, base_atk=8, base_def=14, base_spd=12, base_luck=12,
        blurb="An underappreciated navigator. Remembers a roof from a thousand miles.",
        evolutions=(Evolution("rock_dove_king", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="sparrow", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "rock_dove_king": Species(
        id="rock_dove_king", display_name="Rock Dove King", kind="avian",
        base_hp=24, base_atk=11, base_def=18, base_spd=13, base_luck=13,
        blurb="A crested dove that rules the cliffside rookeries.",
        evolutions=(
            Evolution("ground_titan_bird", requirements={"int_": 62, "luck": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("sky_dove", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="sparrow", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "sky_dove": Species(
        id="sky_dove", display_name="Sky Dove", kind="avian",
        base_hp=34, base_atk=12, base_def=28, base_spd=12, base_luck=16,
        blurb="A storm-cloud dove with silver plumage. Navigates by starlight.",
        sprite_fallback="sparrow", is_starter=False,
    ),
    "thunder_runner": Species(
        id="thunder_runner", display_name="Thunder Runner", kind="avian",
        base_hp=54, base_atk=44, base_def=24, base_spd=46, base_luck=20,
        blurb="A lightning-footed terror bird. Crosses a plain before you can turn.",
        sprite_fallback="sparrow", is_starter=False,
    ),
    "bedrock_runner": Species(
        id="bedrock_runner", display_name="Bedrock Runner", kind="avian",
        base_hp=68, base_atk=30, base_def=46, base_spd=22, base_luck=19,
        blurb="A slate-plated terror bird. Each stomp is an earthquake.",
        sprite_fallback="sparrow", is_starter=False,
    ),

    # ─── ground_titan_bird: SHARED apex (sparrow + chick converge here) ──
    "ground_titan_bird": Species(
        id="ground_titan_bird", display_name="Ground Titan Bird", kind="avian",
        base_hp=46, base_atk=22, base_def=28, base_spd=20, base_luck=26,
        blurb="A flightless colossus with wisdom in its stride. Shared apex for sparrow and chick lines.",
        sprite_fallback="sparrow", is_starter=False,
    ),

    # ─── chick lineage (depth 7) — shares ground_titan_bird with sparrow ──
    "junglefowl": Species(
        id="junglefowl", display_name="Junglefowl", kind="avian",
        base_hp=22, base_atk=9, base_def=16, base_spd=12, base_luck=13,
        blurb="The wild ancestor of chickens. Scratches through underbrush with purpose.",
        evolutions=(Evolution("pheasant_prince", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="chick", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "pheasant_prince": Species(
        id="pheasant_prince", display_name="Pheasant Prince", kind="avian",
        base_hp=26, base_atk=12, base_def=19, base_spd=14, base_luck=14,
        blurb="A crowned forest pheasant with an iridescent tail.",
        evolutions=(
            Evolution("ground_titan_bird", requirements={"int_": 62, "luck": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("prism_pheasant", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="chick", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "prism_pheasant": Species(
        id="prism_pheasant", display_name="Prism Pheasant", kind="avian",
        base_hp=38, base_atk=14, base_def=30, base_spd=13, base_luck=16,
        blurb="Feathers refract light into moving rainbows. A living stained-glass bird.",
        sprite_fallback="chick", is_starter=False,
    ),
    "thunder_moa": Species(
        id="thunder_moa", display_name="Thunder Moa", kind="avian",
        base_hp=58, base_atk=40, base_def=26, base_spd=38, base_luck=20,
        blurb="A stormbound moa with lightning-charged plumage. Its call is a thunderclap.",
        sprite_fallback="chick", is_starter=False,
    ),
    "basalt_moa": Species(
        id="basalt_moa", display_name="Basalt Moa", kind="avian",
        base_hp=72, base_atk=28, base_def=50, base_spd=18, base_luck=18,
        blurb="A basalt-plumed flightless giant. Walks like an obsidian pillar.",
        sprite_fallback="chick", is_starter=False,
    ),

    # ─── duckling lineage (depth 7, no cross-lineage merge) ───────────────
    "grebe_chick": Species(
        id="grebe_chick", display_name="Grebe Chick", kind="avian",
        base_hp=20, base_atk=8, base_def=15, base_spd=12, base_luck=13,
        blurb="A striped diver-in-training. Rides its parent's back across the lake.",
        evolutions=(Evolution("diving_grebe", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="duckling", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "diving_grebe": Species(
        id="diving_grebe", display_name="Diving Grebe", kind="avian",
        base_hp=24, base_atk=11, base_def=18, base_spd=14, base_luck=14,
        blurb="A sleek submarine-bird that vanishes mid-ripple.",
        evolutions=(
            Evolution("deep_diver", requirements={"atk": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("stone_diver", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="duckling", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "deep_diver": Species(
        id="deep_diver", display_name="Deep Diver", kind="avian",
        base_hp=34, base_atk=26, base_def=20, base_spd=28, base_luck=16,
        blurb="A cold-lake specialist that hunts fish a hundred feet down.",
        sprite_fallback="duckling", is_starter=False,
    ),
    "stone_diver": Species(
        id="stone_diver", display_name="Stone Diver", kind="avian",
        base_hp=42, base_atk=14, base_def=34, base_spd=12, base_luck=16,
        blurb="A dense-boned diver bird. Sinks by choice, surfaces by will.",
        sprite_fallback="duckling", is_starter=False,
    ),
    "thunder_seabird": Species(
        id="thunder_seabird", display_name="Thunder Seabird", kind="avian",
        base_hp=54, base_atk=38, base_def=26, base_spd=42, base_luck=20,
        blurb="A storm-chasing pelagornis. Its wake shreds the crests.",
        sprite_fallback="duckling", is_starter=False,
    ),
    "cavern_seabird": Species(
        id="cavern_seabird", display_name="Cavern Seabird", kind="avian",
        base_hp=66, base_atk=26, base_def=46, base_spd=22, base_luck=19,
        blurb="A cliff-cave seabird with hide like weathered stone.",
        sprite_fallback="duckling", is_starter=False,
    ),
}


def get(species_id: str) -> Species:
    if species_id not in SPECIES:
        raise KeyError(f"unknown species: {species_id!r}")
    return SPECIES[species_id]


def all_species() -> list[Species]:
    return list(SPECIES.values())


def random_starters(n: int = 3) -> list[Species]:
    """Sample n distinct starter species (excluding evolved forms)."""
    pool = [sp for sp in SPECIES.values() if sp.is_starter]
    if n >= len(pool):
        return pool
    return random.sample(pool, n)


def get_dominant_stat(stats: "Stats") -> str:
    """Return the non-HP stat with the highest value. Ties broken by the
    priority order atk > def_ > spd > luck > int_ > res. Used by quests
    (e.g. INT-dominant buddies can mana-cast for a success boost).
    """
    best_name = _DOMINANCE_PRIORITY[0]
    best_val = -1
    for name in _DOMINANCE_PRIORITY:
        val = getattr(stats, name)
        if val > best_val:
            best_val = val
            best_name = name
    return best_name


def branch_eligibility(evo: "Evolution", stats: "Stats") -> dict:
    """Return per-branch eligibility info for an Evolution against a buddy's
    Stats. The branch is eligible only when every entry in `evo.requirements`
    is satisfied. Returned dict carries per-stat checks suitable for direct
    rendering in the UI.
    """
    target = get(evo.evolved_species_id)
    checks: list[dict] = []
    eligible = True
    for stat_key, required in evo.requirements.items():
        actual = getattr(stats, stat_key)
        met = actual >= required
        if not met:
            eligible = False
        checks.append({
            "stat": stat_key.rstrip("_"),
            "required": required,
            "actual": actual,
            "met": met,
        })
    return {
        "species_id": evo.evolved_species_id,
        "display_name": target.display_name,
        "checks": checks,
        "eligible": eligible,
    }


def _compute_tiers() -> dict[str, int]:
    """Walk the evolution DAG and assign a tier to every species. Starters
    are tier 0; each evolution step increases the tier by one. Convergent
    nodes (reached from multiple parents) get the maximum parent tier + 1,
    so the computed tier reflects the deepest path to that species."""
    tiers: dict[str, int] = {sp.id: 0 for sp in SPECIES.values() if sp.is_starter}
    changed = True
    while changed:
        changed = False
        for sp in SPECIES.values():
            if sp.id not in tiers:
                continue
            for evo in sp.evolutions:
                candidate = tiers[sp.id] + 1
                if tiers.get(evo.evolved_species_id, -1) < candidate:
                    tiers[evo.evolved_species_id] = candidate
                    changed = True
    return tiers


_TIERS: dict[str, int] = _compute_tiers()


def get_tier(species_id: str) -> int:
    """Return the evolution tier of a species (0 = starter, up to 4 for
    the deepest current lineages)."""
    return _TIERS.get(species_id, 0)


def _assign_mythic_levels() -> None:
    """Sweep SPECIES and set `mythic_at = 20` on every terminal non-starter
    species. Works at any tier depth — tier-2 legacy terminals, tier-4 most
    lineages, tier-5/6 branch-pair apices. Lets new branches at arbitrary
    tier depth automatically participate in the mythic ladder with no
    per-tier config.
    """
    from dataclasses import replace
    for sp_id, sp in list(SPECIES.items()):
        if sp.is_starter or sp.evolves_at is not None or sp.evolutions:
            continue  # only apex (terminal non-starter) species qualify
        SPECIES[sp_id] = replace(sp, mythic_at=20)


_assign_mythic_levels()


@dataclass
class Sprite:
    idle_frames: list[list[str]]
    quest_frames: list[list[str]] = field(default_factory=list)


_SPRITE_CACHE: dict[str, Sprite] = {}
_SHARED_QUEST_CACHE: Optional[list[list[str]]] = None


def _parse_sprite_file(text: str) -> Sprite:
    """Parse a sprite .txt file into idle / quest frame banks.

    Frames inside each bank are delimited by a line containing only
    `--FRAME--`. The optional `--QUEST--` marker (also on its own line)
    switches subsequent frames from the idle bank into the quest bank.
    Leading/trailing blank lines on each frame are trimmed.
    """
    idle: list[list[str]] = []
    quest: list[list[str]] = []
    current_bank = idle
    buf: list[str] = []
    for raw in text.splitlines():
        marker = raw.strip()
        if marker == "--FRAME--":
            if buf:
                current_bank.append(buf)
                buf = []
            continue
        if marker == "--QUEST--":
            if buf:
                current_bank.append(buf)
                buf = []
            current_bank = quest
            continue
        buf.append(raw)
    if buf:
        current_bank.append(buf)

    def _trim(frame: list[str]) -> list[str]:
        while frame and not frame[0].strip():
            frame.pop(0)
        while frame and not frame[-1].strip():
            frame.pop()
        return frame

    return Sprite(
        idle_frames=[f for f in (_trim(f) for f in idle) if f],
        quest_frames=[f for f in (_trim(f) for f in quest) if f],
    )


def _load_sprite(species_id: str) -> Sprite:
    if species_id in _SPRITE_CACHE:
        return _SPRITE_CACHE[species_id]
    path = Path(__file__).parent / "sprites" / f"{species_id}.txt"
    if not path.exists():
        # Fall back to a preevolution's sprite when this species ships without
        # its own art (common for evolved forms). Cache the fallback result
        # under the original species id so subsequent lookups are O(1).
        sp = SPECIES.get(species_id)
        if sp and sp.sprite_fallback:
            fallback = _load_sprite(sp.sprite_fallback)
            _SPRITE_CACHE[species_id] = fallback
            return fallback
    sprite = _parse_sprite_file(path.read_text())
    if not sprite.idle_frames:
        # Defensive: an empty or mangled sprite file becomes a single empty
        # frame so callers always have at least one frame to render.
        sprite = Sprite(idle_frames=[[""]])
    _SPRITE_CACHE[species_id] = sprite
    return sprite


def sprite_frames(species_id: str) -> list[list[str]]:
    """Return the species's idle frame list (1+ frames, each a list of lines)."""
    return _load_sprite(species_id).idle_frames


def species_motion_frames(species_id: str) -> list[list[str]]:
    """Return the species's own motion frames (from the --QUEST-- bank of
    its sprite file), or an empty list if the species has no motion bank.
    Callers should fall back to `quest_sprite_frames()` (shared) when this
    returns an empty list.
    """
    return _load_sprite(species_id).quest_frames


def quest_sprite_frames() -> list[list[str]]:
    """Return the shared 'away on quest' frames, or an empty list if the
    shared sprite file is missing. Callers should fall back to species idle
    frames when this returns an empty list.
    """
    global _SHARED_QUEST_CACHE
    if _SHARED_QUEST_CACHE is not None:
        return _SHARED_QUEST_CACHE
    path = Path(__file__).parent / "sprites" / "_quest.txt"
    try:
        text = path.read_text()
    except FileNotFoundError:
        _SHARED_QUEST_CACHE = []
        return _SHARED_QUEST_CACHE
    sprite = _parse_sprite_file(text)
    # The shared file has no species identity; every frame in it is used
    # as a quest frame regardless of which bank the parser put it in.
    _SHARED_QUEST_CACHE = sprite.idle_frames + sprite.quest_frames
    return _SHARED_QUEST_CACHE
