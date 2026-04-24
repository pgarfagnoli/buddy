"""Starter species registry with base stats and ASCII sprites."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import paths

if TYPE_CHECKING:
    from state import Stats


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
            Evolution("kakapo", requirements={"def_": 8, "luck": 8}, stat_bonus=_TIER_2_BONUS),
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
        inherent_skills=("scout",),  # carried over from rabbit pre-evolution
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
        evolutions=(Evolution("capybara", requirements={"luck": 16}, stat_bonus=_TIER_2_BONUS), Evolution("glacier_rat", requirements={"hp": 28, "res": 28}, stat_bonus=_TIER_3_BONUS),),
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
        evolutions=(
            Evolution("giant_hornet", requirements={"atk": 16}, stat_bonus=_TIER_2_BONUS),
            Evolution("praying_mantis", requirements={"atk": 16, "spd": 16}, stat_bonus=_TIER_3_BONUS),
        ),
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
        evolutions=(
            Evolution("cane_toad", requirements={"spd": 16}, stat_bonus=_TIER_2_BONUS),
            Evolution("purple_frog", requirements={"def_": 16, "res": 16}, stat_bonus=_TIER_3_BONUS),
        ),
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
        evolutions=(
            Evolution("alligator_snapping_turtle", requirements={"def_": 16}, stat_bonus=_TIER_2_BONUS),
            Evolution("leatherback_turtle", requirements={"def_": 16, "hp": 16}, stat_bonus=_TIER_3_BONUS),
        ),
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
            Evolution("cave_mole", requirements={"def_": 16, "res": 16}, stat_bonus=_TIER_4_BONUS),
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
        inherent_skills=("hearty",),  # granted on evolution from porcupine
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
        ),
        sprite_fallback="baby_gecko", is_starter=False, evolves_at=TIER_3_LEVEL,
    ),
    "alligator_snapping_turtle": Species(
        id="alligator_snapping_turtle", display_name="Alligator Snapping Turtle", kind="reptile",
        base_hp=25, base_atk=13, base_def=18, base_spd=5, base_luck=8,
        blurb="A prehistoric jaw. Tongue-lure like a worm. Do not investigate.",
        evolutions=(            Evolution("baby_crocodile", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
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
        evolutions=(            Evolution("fat_tail_lizard", requirements={"def_": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),
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
        inherent_skills=("vicious_strike",),  # granted on evolution from flounder
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
        evolutions=(
            Evolution("harpy_eagle", requirements={"atk": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("bald_eagle", requirements={"hp": 44, "atk": 44}, stat_bonus=_TIER_4_BONUS),
            Evolution("philippine_eagle", requirements={"atk": 44, "spd": 44}, stat_bonus=_TIER_6_BONUS),
        ),
        sprite_fallback="wren", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "mako_shark": Species(
        id="mako_shark", display_name="Mako Shark", kind="aquatic",
        base_hp=23, base_atk=21, base_def=13, base_spd=22, base_luck=13,
        blurb="The fastest shark alive. Breaches like a missile, outruns its own prey.",
        evolutions=(
            Evolution("great_white_shark", requirements={"spd": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("livyatan", requirements={"atk": 62, "hp": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("frilled_shark", requirements={"int_": 28, "luck": 28}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="guppy", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),

    # ant line tier-3 / tier-4 extensions
    "bullet_ant": Species(
        id="bullet_ant", display_name="Bullet Ant", kind="insect",
        base_hp=24, base_atk=18, base_def=15, base_spd=12, base_luck=8,
        blurb="The most painful sting on record. One is an event; a nest is a catastrophe.",
        evolutions=(
            Evolution("titanomyrma", requirements={"atk": 44}, stat_bonus=_TIER_4_BONUS),
            Evolution("vinegaroon", requirements={"int_": 28, "luck": 28}, stat_bonus=_TIER_5_BONUS),
        ),
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
            Evolution("goliath_birdeater", requirements={"atk": 44, "hp": 44}, stat_bonus=_TIER_4_BONUS),
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
        evolutions=(Evolution("koolasuchus", requirements={"atk": 44}, stat_bonus=_TIER_4_BONUS), Evolution("pacman_frog", requirements={"atk": 28, "luck": 28}, stat_bonus=_TIER_3_BONUS),),
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
         Evolution("surinam_horned_frog", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="froglet", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "mudpuppy": Species(
        id="mudpuppy", display_name="Mudpuppy", kind="amphibian",
        base_hp=27, base_atk=13, base_def=17, base_spd=10, base_luck=12,
        blurb="A gilled river salamander. Never grows up, never stops hunting.",
        evolutions=(Evolution("japanese_giant_salamander", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS), Evolution("amphiuma", requirements={"def_": 28, "res": 28}, stat_bonus=_TIER_3_BONUS),),
        sprite_fallback="newt", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "japanese_giant_salamander": Species(
        id="japanese_giant_salamander", display_name="Japanese Giant Salamander", kind="amphibian",
        base_hp=33, base_atk=16, base_def=21, base_spd=10, base_luck=13,
        blurb="Five feet long, called 'giant pepper fish' for the milky ooze it weeps when alarmed.",
        evolutions=(
            Evolution("mountain_salamander", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),        ),
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
         Evolution("andrias_scheuchzeri", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
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
        evolutions=(Evolution("elephant_bird", requirements={"atk": 62}, stat_bonus=_TIER_5_BONUS), Evolution("sky_dove", requirements={"spd": 44, "luck": 44}, stat_bonus=_TIER_4_BONUS),),
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
         Evolution("madagascar_day_gecko", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
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
         Evolution("rhinoceros_iguana", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="anole", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "megalania": Species(
        id="megalania", display_name="Giant Monitor Lizard", kind="reptile",
        base_hp=27, base_atk=21, base_def=17, base_spd=13, base_luck=9,
        blurb="An extinct 23-foot monitor lizard. The largest goanna that ever walked Australia.",
        evolutions=(Evolution("mosasaur", requirements={"atk": 44}, stat_bonus=_TIER_4_BONUS), Evolution("gila_monster", requirements={"def_": 28, "res": 28}, stat_bonus=_TIER_3_BONUS),),
        sprite_fallback="skink", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "mosasaur": Species(
        id="mosasaur", display_name="Prehistoric Sea Lizard", kind="reptile",
        base_hp=33, base_atk=25, base_def=20, base_spd=15, base_luck=10,
        blurb="An extinct sea-lizard, 50 feet long. Apex predator of the late cretaceous oceans.",
        evolutions=(Evolution("tylosaurus", requirements={"atk": 62}, stat_bonus=_TIER_5_BONUS), Evolution("basilosaurus", requirements={"hp": 62, "spd": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="skink", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),

    # lagomorph apex continuation
    "nuralagus": Species(
        id="nuralagus", display_name="Island Giant Rabbit", kind="beast",
        base_hp=30, base_atk=13, base_def=13, base_spd=18, base_luck=12,
        blurb="An extinct fox-sized rabbit from Minorca. Slow-hopping, no predators, unafraid.",
        evolutions=(         Evolution("secretary_bird", requirements={"spd": 28, "atk": 28}, stat_bonus=_TIER_5_BONUS),),
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
        sprite_fallback="wren", is_starter=False,
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
         Evolution("helicoprion", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="guppy", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),

    # ─── tier-5 extensions (Lv 55) ─────────────────────────────────────────
    # Prehistoric / extinct giants; each continues to a tier-6 terminal apex.
    "phoberomys": Species(
        id="phoberomys", display_name="Ancient Giant Rodent", kind="beast",
        base_hp=36, base_atk=16, base_def=18, base_spd=10, base_luck=13,
        blurb="A prehistoric rodent the size of a buffalo. Roamed the Venezuelan wetlands.",
        evolutions=(Evolution("josephoartigasia", requirements={"def_": 80}, stat_bonus=_TIER_6_BONUS), Evolution("paraceratherium", requirements={"def_": 62, "hp": 62}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="field_mouse", is_starter=False, evolves_at=TIER_6_LEVEL,
    ),
    "doedicurus": Species(
        id="doedicurus", display_name="Mace-Tailed Armadillo", kind="beast",
        base_hp=38, base_atk=17, base_def=28, base_spd=8, base_luck=11,
        blurb="An extinct armored giant. Tail ended in a spiked mace for dueling its own kind.",
        evolutions=(Evolution("megatherium", requirements={"def_": 80}, stat_bonus=_TIER_6_BONUS), Evolution("woolly_mammoth", requirements={"hp": 80, "def_": 80}, stat_bonus=_TIER_5_BONUS),),
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
        evolutions=(Evolution("colossal_squid", requirements={"atk": 80}, stat_bonus=_TIER_6_BONUS), Evolution("cameroceras", requirements={"def_": 44, "int_": 44}, stat_bonus=_TIER_4_BONUS),),
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
         Evolution("castoroides", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="field_mouse", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "megatherium": Species(
        id="megatherium", display_name="Giant Ground Sloth", kind="beast",
        base_hp=45, base_atk=22, base_def=33, base_spd=8, base_luck=13,
        blurb="A 20-foot Ice Age sloth the weight of an elephant. Clawed its lunch out of trees.",
        evolutions=(
         Evolution("eremotherium", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="hedgehog", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "pulmonoscorpius": Species(
        id="pulmonoscorpius", display_name="Giant Land Scorpion", kind="insect",
        base_hp=38, base_atk=30, base_def=26, base_spd=13, base_luck=15,
        blurb="A meter-long prehistoric land scorpion. Lung-breathers from before there were birds.",
        sprite_fallback="ladybug", is_starter=False,
    ),
    "meganeuropsis": Species(
        id="meganeuropsis", display_name="Titan Dragonfly", kind="insect",
        base_hp=39, base_atk=18, base_def=26, base_spd=17, base_luck=15,
        blurb="The largest insect that ever lived — 71cm of iridescent, silent death.",
        evolutions=(
         Evolution("mongolarachne", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="caterpillar", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "mastodonsaurus": Species(
        id="mastodonsaurus", display_name="Jaw-Tooth Amphibian", kind="amphibian",
        base_hp=40, base_atk=30, base_def=26, base_spd=16, base_luck=14,
        blurb="A 6-meter extinct amphibian with tusks that pierced its own skull to fit shut.",
        evolutions=(
         Evolution("lethiscus", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="tadpole", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "dunkleosteus": Species(
        id="dunkleosteus", display_name="Armored Prehistoric Fish", kind="aquatic",
        base_hp=40, base_atk=31, base_def=25, base_spd=24, base_luck=13,
        blurb="A Devonian armored fish with self-sharpening blade-plates for teeth.",
        evolutions=(
         Evolution("titanichthys", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="minnow", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "colossal_squid": Species(
        id="colossal_squid", display_name="Colossal Squid", kind="aquatic",
        base_hp=36, base_atk=27, base_def=20, base_spd=20, base_luck=19,
        blurb="Bigger than a giant squid. Swivel hooks on each arm. Eyes the size of dinner plates.",
        evolutions=(
         Evolution("tusoteuthis", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="snail", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "jaekelopterus": Species(
        id="jaekelopterus", display_name="Giant Sea Scorpion", kind="aquatic",
        base_hp=38, base_atk=32, base_def=24, base_spd=18, base_luck=14,
        blurb="The largest arthropod that ever lived — 2.5 meters of aquatic pincer.",
        evolutions=(
         Evolution("pterygotus", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="shrimp", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "phorusrhacos": Species(
        id="phorusrhacos", display_name="Terror Bird", kind="avian",
        base_hp=36, base_atk=29, base_def=17, base_spd=24, base_luck=16,
        blurb="A 3-meter flightless carnivore with a beak like an axe. South America's nightmare.",
        evolutions=(
         Evolution("kelenken", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="sparrow", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "moa": Species(
        id="moa", display_name="Moa", kind="avian",
        base_hp=42, base_atk=27, base_def=21, base_spd=22, base_luck=15,
        blurb="A 12-foot flightless giant from New Zealand. Extinct within 100 years of human arrival.",
        evolutions=(
         Evolution("bullockornis", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="chick", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "pelagornis": Species(
        id="pelagornis", display_name="Toothed Giant Seabird", kind="avian",
        base_hp=38, base_atk=26, base_def=22, base_spd=25, base_luck=15,
        blurb="A 7-meter wingspan and a beak lined with bony 'teeth'. Extinct 3 million years.",
        evolutions=(Evolution("osteodontornis", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="duckling", is_starter=False,
    ),
    "meiolania": Species(
        id="meiolania", display_name="Horned Giant Turtle", kind="reptile",
        base_hp=46, base_atk=24, base_def=35, base_spd=10, base_luck=12,
        blurb="An extinct island turtle with horns on its skull and a spiked club tail.",
        evolutions=(
         Evolution("protostega", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="hatchling_turtle", is_starter=False, evolves_at=TIER_7_LEVEL,
    ),
    "liopleurodon": Species(
        id="liopleurodon", display_name="Giant Marine Reptile", kind="reptile",
        base_hp=44, base_atk=34, base_def=27, base_spd=20, base_luck=12,
        blurb="A 7-meter Jurassic pliosaur. Crocodile-headed terror of the ancient oceans.",
        evolutions=(
         Evolution("prognathodon", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
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
        evolutions=(Evolution("myrmecia_bull_ant", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
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
        ),
        sprite_fallback="ant", is_starter=False, evolves_at=TIER_5_LEVEL,
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
        ),
        sprite_fallback="rabbit", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "tundra_lynx": Species(
        id="tundra_lynx", display_name="Tundra Lynx", kind="beast",
        base_hp=34, base_atk=22, base_def=16, base_spd=24, base_luck=14,
        blurb="A snow-pawed sprint hunter with tufted ears and silent feet.",
        evolutions=(Evolution("smilodon", requirements={"atk": 44, "spd": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="rabbit", is_starter=False,
    ),
    # ─── tadpole lineage (depth 7, tier-3 short branch + tier-7 apex branch) ─
    "sea_eel": Species(
        id="sea_eel", display_name="Sea Eel", kind="amphibian",
        base_hp=26, base_atk=17, base_def=17, base_spd=16, base_luck=11,
        blurb="A river-to-ocean rogue. Electric through the dark.",
        evolutions=(
        ),
        sprite_fallback="tadpole", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    # ─── hatchling_turtle lineage (depth 7, tier-3 crocodile branch + tier-7 apex branch) ─
    "baby_crocodile": Species(
        id="baby_crocodile", display_name="Baby Crocodile", kind="reptile",
        base_hp=22, base_atk=14, base_def=15, base_spd=9, base_luck=9,
        blurb="A palm-sized ambush predator. Already knows how to wait.",
        evolutions=(Evolution("nile_croc", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS), Evolution("gharial", requirements={"spd": 28, "int_": 28}, stat_bonus=_TIER_3_BONUS),),
        sprite_fallback="hatchling_turtle", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "nile_croc": Species(
        id="nile_croc", display_name="Nile Crocodile", kind="reptile",
        base_hp=28, base_atk=20, base_def=19, base_spd=11, base_luck=10,
        blurb="Four meters of ambush and bite. Doesn't miss its first lunge.",
        evolutions=(
            Evolution("armored_caiman", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS),
            Evolution("saltwater_crocodile", requirements={"hp": 62, "atk": 62}, stat_bonus=_TIER_5_BONUS),
        ),
        sprite_fallback="hatchling_turtle", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "armored_caiman": Species(
        id="armored_caiman", display_name="Armored Caiman", kind="reptile",
        base_hp=42, base_atk=22, base_def=32, base_spd=14, base_luck=12,
        blurb="Bone-plated from snout to tail. A pond-bottom fortress.",
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
            Evolution("whale_shark", requirements={"hp": 44, "def_": 44}, stat_bonus=_TIER_6_BONUS),
        ),
        sprite_fallback="minnow", is_starter=False, evolves_at=TIER_5_LEVEL,
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
        ),
        sprite_fallback="wren", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    # ═════════════════════════════════════════════════════════════════════
    # Split-and-converge — batch 2: beasts (field_mouse, squirrel, hedgehog)
    # ═════════════════════════════════════════════════════════════════════

    # ─── field_mouse lineage (depth 7) ────────────────────────────────────
    "shrew_hunter": Species(
        id="shrew_hunter", display_name="Shrew Hunter", kind="beast",
        base_hp=22, base_atk=11, base_def=15, base_spd=12, base_luck=10,
        blurb="A tiny insectivore with a venomous bite and a relentless appetite.",
        evolutions=(Evolution("mountain_mole", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="field_mouse", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "glacier_rat": Species(
        id="glacier_rat", display_name="Glacier Rat", kind="beast",
        base_hp=40, base_atk=18, base_def=30, base_spd=12, base_luck=13,
        blurb="A white-furred tundra burrower. Its bones are said to conduct cold.",
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
            Evolution("dire_wolf", requirements={"atk": 44, "hp": 44}, stat_bonus=_TIER_4_BONUS),
            Evolution("tundra_lynx", requirements={"hp": 28, "atk": 28}, stat_bonus=_TIER_4_BONUS),
        ),
        sprite_fallback="squirrel", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    # ─── alpine_colossus: SHARED apex (field_mouse + squirrel converge here) ─
    # ─── hedgehog lineage (depth 7) ───────────────────────────────────────
    "mountain_mole": Species(
        id="mountain_mole", display_name="Mountain Mole", kind="beast",
        base_hp=24, base_atk=9, base_def=18, base_spd=8, base_luck=10,
        blurb="A boulder-dwelling digger. Sharper hearing than sight, which is saying something.",
        evolutions=( Evolution("andrewsarchus", requirements={"atk": 44, "hp": 44}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="hedgehog", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "cave_mole": Species(
        id="cave_mole", display_name="Cave Mole", kind="beast",
        base_hp=30, base_atk=12, base_def=24, base_spd=9, base_luck=11,
        blurb="A blind stonework specialist. Lives in caverns no one else has seen.",
        evolutions=(
        ),
        sprite_fallback="hedgehog", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    # ═════════════════════════════════════════════════════════════════════
    # Split-and-converge — batch 3: insects (bee, ladybug, caterpillar)
    # Shared apex: titan_wing_beetle (ladybug + caterpillar converge)
    # ═════════════════════════════════════════════════════════════════════

    # ─── bee lineage (depth 5, no cross-lineage merge) ────────────────────
    # ─── ladybug lineage (depth 7) — shares titan_wing_beetle with caterpillar ─
    "glow_bug": Species(
        id="glow_bug", display_name="Glow Bug", kind="insect",
        base_hp=22, base_atk=10, base_def=14, base_spd=8, base_luck=14,
        blurb="A beetle that carries its own lantern. Blinks in code.",
        evolutions=(Evolution("hercules_beetle", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="ladybug", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    # ─── titan_wing_beetle: SHARED apex (ladybug + caterpillar converge here) ─
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
        ),
        sprite_fallback="caterpillar", is_starter=False, evolves_at=TIER_5_LEVEL,
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
        evolutions=(Evolution("amazon_toad", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS), Evolution("sea_eel", requirements={"spd": 28, "luck": 28}, stat_bonus=_TIER_3_BONUS),),
        sprite_fallback="froglet", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "amazon_toad": Species(
        id="amazon_toad", display_name="Amazon Toad", kind="amphibian",
        base_hp=26, base_atk=12, base_def=17, base_spd=13, base_luck=12,
        blurb="Jungle-canopy ruler with a pocket of tadpoles on its back.",
        evolutions=(
        ),
        sprite_fallback="froglet", is_starter=False, evolves_at=TIER_5_LEVEL,
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
        ),
        sprite_fallback="newt", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "mountain_salamander": Species(
        id="mountain_salamander", display_name="Mountain Salamander", kind="amphibian",
        base_hp=48, base_atk=18, base_def=36, base_spd=10, base_luck=15,
        blurb="A granite-skinned giant. Lives in cold mountain springs for centuries.",
        evolutions=(Evolution("sclerocephalus", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="newt", is_starter=False,
    ),

    # ─── elder_salamander: SHARED apex (newt + axolotl converge here) ────
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
            Evolution("iron_puffer", requirements={"def_": 62, "res": 62}, stat_bonus=_TIER_5_BONUS, grants_skill="iron_skin"),
        ),
        sprite_fallback="guppy", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    "iron_puffer": Species(
        id="iron_puffer", display_name="Iron Puffer", kind="aquatic",
        base_hp=40, base_atk=14, base_def=32, base_spd=8, base_luck=14,
        blurb="Inflates into a sphere of living iron. A reef's immovable gate.",
        inherent_skills=("iron_skin",),  # granted on evolution from pufferfish
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
        ),
        sprite_fallback="snail", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    # ─── deep_crustacean: SHARED apex (snail + shrimp converge here) ──────
    # ─── shrimp lineage (depth 7) — shares deep_crustacean with snail ─────
    "pistol_shrimp": Species(
        id="pistol_shrimp", display_name="Pistol Shrimp", kind="aquatic",
        base_hp=22, base_atk=13, base_def=17, base_spd=13, base_luck=12,
        blurb="Snaps its claw to shoot a cavitation bullet. Louder than a gunshot.",
        evolutions=(Evolution("mantis_shrimp", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="shrimp", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    # ═════════════════════════════════════════════════════════════════════
    # Split-and-converge — batch 6: reptiles (baby_gecko, anole, skink)
    # Shared apex: monitor_titan (anole + skink converge)
    # ═════════════════════════════════════════════════════════════════════

    # ─── baby_gecko lineage (depth 5, no cross-lineage merge) ─────────────
    "glass_lizard": Species(
        id="glass_lizard", display_name="Glass Lizard", kind="reptile",
        base_hp=24, base_atk=11, base_def=19, base_spd=13, base_luck=13,
        blurb="A legless lizard that drops its tail like shattering glass.",
        evolutions=(
        ),
        sprite_fallback="baby_gecko", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    # ─── anole lineage (depth 5) — shares monitor_titan with skink ────────
    "small_varanid": Species(
        id="small_varanid", display_name="Small Varanid", kind="reptile",
        base_hp=22, base_atk=10, base_def=16, base_spd=13, base_luck=12,
        blurb="A palm-sized monitor lizard. Hunts like its giant cousins in miniature.",
        evolutions=(Evolution("tree_monitor", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS), Evolution("glass_lizard", requirements={"spd": 28, "luck": 28}, stat_bonus=_TIER_3_BONUS),),
        sprite_fallback="anole", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "tree_monitor": Species(
        id="tree_monitor", display_name="Tree Monitor", kind="reptile",
        base_hp=26, base_atk=13, base_def=20, base_spd=15, base_luck=13,
        blurb="An arboreal monitor with whip-tail and emerald scales.",
        evolutions=(
        ),
        sprite_fallback="anole", is_starter=False, evolves_at=TIER_5_LEVEL,
    ),
    # ─── monitor_titan: SHARED apex (anole + skink converge here) ─────────
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
            Evolution("anaconda", requirements={"atk": 44, "hp": 44}, stat_bonus=_TIER_4_BONUS),
            Evolution("megalania", requirements={"def_": 44, "hp": 44}, stat_bonus=_TIER_6_BONUS),
        ),
        sprite_fallback="skink", is_starter=False, evolves_at=TIER_5_LEVEL,
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
        evolutions=(Evolution("pelagornis", requirements={"def_": 44}, stat_bonus=_TIER_4_BONUS),),
        sprite_fallback="sparrow", is_starter=False, evolves_at=TIER_4_LEVEL,
    ),
    "sky_dove": Species(
        id="sky_dove", display_name="Sky Dove", kind="avian",
        base_hp=34, base_atk=12, base_def=28, base_spd=12, base_luck=16,
        blurb="A storm-cloud dove with silver plumage. Navigates by starlight.",
        sprite_fallback="sparrow", is_starter=False,
    ),
    # ─── ground_titan_bird: SHARED apex (sparrow + chick converge here) ──
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
        ),
        sprite_fallback="chick", is_starter=False, evolves_at=TIER_5_LEVEL,
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
        sprite_fallback="duckling", is_starter=False,
    ),

    # ─── Phase 3 additions: real apex species across kinds ─────────────────
    # beasts (extinct megafauna + apex predators)
    "smilodon": Species(
        id="smilodon", display_name="Smilodon", kind="beast",
        base_hp=44, base_atk=34, base_def=22, base_spd=20, base_luck=14,
        blurb="A saber-toothed cat. The dagger fangs do not whistle when they swing.",
        evolutions=(Evolution("thylacosmilus", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="hare", is_starter=False,
    ),
    "dire_wolf": Species(
        id="dire_wolf", display_name="Dire Wolf", kind="beast",
        base_hp=42, base_atk=30, base_def=20, base_spd=24, base_luck=15,
        blurb="A pack-hunting ice age canid. Heavier and meaner than its modern cousins.",
        evolutions=(Evolution("cave_lion", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="hare", is_starter=False,
    ),
    "paraceratherium": Species(
        id="paraceratherium", display_name="Paraceratherium", kind="beast",
        base_hp=68, base_atk=24, base_def=42, base_spd=10, base_luck=12,
        blurb="The largest land mammal that ever lived. A hornless rhino the size of a house.",
        sprite_fallback="hare", is_starter=False,
    ),
    "andrewsarchus": Species(
        id="andrewsarchus", display_name="Andrewsarchus", kind="beast",
        base_hp=50, base_atk=36, base_def=24, base_spd=18, base_luck=14,
        blurb="A bone-crushing carnivorous mammal from the Eocene. Skull longer than a wolf.",
        sprite_fallback="hare", is_starter=False,
    ),
    "woolly_mammoth": Species(
        id="woolly_mammoth", display_name="Woolly Mammoth", kind="beast",
        base_hp=72, base_atk=28, base_def=44, base_spd=12, base_luck=13,
        blurb="A shaggy ice age titan. Tusks the length of a fishing pole.",
        sprite_fallback="hare", is_starter=False,
    ),

    # aquatic (extinct + extant marine apex)
    "basilosaurus": Species(
        id="basilosaurus", display_name="Basilosaurus", kind="aquatic",
        base_hp=58, base_atk=32, base_def=24, base_spd=22, base_luck=14,
        blurb="An eel-shaped early whale. Sixty feet of toothed coil through warm Eocene seas.",
        sprite_fallback="guppy", is_starter=False,
    ),
    "livyatan": Species(
        id="livyatan", display_name="Livyatan", kind="aquatic",
        base_hp=60, base_atk=38, base_def=22, base_spd=20, base_luck=15,
        blurb="A macropredator sperm whale, extinct. Hunted other whales for breakfast.",
        sprite_fallback="guppy", is_starter=False,
    ),
    "cameroceras": Species(
        id="cameroceras", display_name="Cameroceras", kind="aquatic",
        base_hp=46, base_atk=24, base_def=32, base_spd=14, base_luck=16,
        blurb="A giant orthocone. A thirty-foot ice cream cone with tentacles and a temper.",
        sprite_fallback="guppy", is_starter=False,
    ),
    "whale_shark": Species(
        id="whale_shark", display_name="Whale Shark", kind="aquatic",
        base_hp=64, base_atk=18, base_def=36, base_spd=18, base_luck=15,
        blurb="The largest extant fish. A polka-dotted suction-feeder you can swim alongside.",
        sprite_fallback="guppy", is_starter=False,
    ),
    "frilled_shark": Species(
        id="frilled_shark", display_name="Frilled Shark", kind="aquatic",
        base_hp=38, base_atk=24, base_def=20, base_spd=22, base_luck=14,
        blurb="A living fossil shark with three hundred backward-curving teeth.",
        sprite_fallback="guppy", is_starter=False,
    ),

    # insects / arachnids
    "praying_mantis": Species(
        id="praying_mantis", display_name="Praying Mantis", kind="insect",
        base_hp=22, base_atk=22, base_def=10, base_spd=20, base_luck=14,
        blurb="A patient ambush hunter. Strikes faster than the eye can register.",
        sprite_fallback="ant", is_starter=False,
    ),
    "goliath_birdeater": Species(
        id="goliath_birdeater", display_name="Goliath Birdeater", kind="insect",
        base_hp=34, base_atk=22, base_def=18, base_spd=14, base_luck=13,
        blurb="The world's largest spider. A foot across with leg-hairs that itch on contact.",
        evolutions=(Evolution("brazilian_wandering_spider", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="ant", is_starter=False,
    ),
    "vinegaroon": Species(
        id="vinegaroon", display_name="Vinegaroon", kind="insect",
        base_hp=24, base_atk=14, base_def=20, base_spd=12, base_luck=15,
        blurb="A whip scorpion that sprays acetic acid when alarmed. Smells like a salad.",
        sprite_fallback="ant", is_starter=False,
    ),

    # avian (extant raptors + flightless oddballs)
    "secretary_bird": Species(
        id="secretary_bird", display_name="Secretary Bird", kind="avian",
        base_hp=36, base_atk=26, base_def=18, base_spd=24, base_luck=15,
        blurb="A long-legged ground raptor. Stomps snakes flat with surgical kicks.",
        sprite_fallback="sparrow", is_starter=False,
    ),
    "philippine_eagle": Species(
        id="philippine_eagle", display_name="Philippine Eagle", kind="avian",
        base_hp=46, base_atk=34, base_def=22, base_spd=28, base_luck=16,
        blurb="A monkey-eating crested eagle. One of the largest extant raptors.",
        evolutions=(Evolution("argentavis_apex", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="sparrow", is_starter=False,
    ),
    "kakapo": Species(
        id="kakapo", display_name="Kakapo", kind="avian",
        base_hp=28, base_atk=10, base_def=22, base_spd=8, base_luck=20,
        blurb="A flightless nocturnal parrot from New Zealand. Heavy, fluffy, and accidentally charming.",
        sprite_fallback="sparrow", is_starter=False,
    ),
    "bald_eagle": Species(
        id="bald_eagle", display_name="Bald Eagle", kind="avian",
        base_hp=38, base_atk=28, base_def=18, base_spd=26, base_luck=15,
        blurb="A white-headed fish hawk with a six-foot wingspan and an attitude.",
        sprite_fallback="sparrow", is_starter=False,
    ),

    # reptiles
    "saltwater_crocodile": Species(
        id="saltwater_crocodile", display_name="Saltwater Crocodile", kind="reptile",
        base_hp=64, base_atk=34, base_def=32, base_spd=14, base_luck=14,
        blurb="The largest extant reptile. Bites with the strongest jaws ever measured.",
        sprite_fallback="baby_gecko", is_starter=False,
    ),
    "gharial": Species(
        id="gharial", display_name="Gharial", kind="reptile",
        base_hp=42, base_atk=24, base_def=22, base_spd=20, base_luck=14,
        blurb="A slim-snouted river crocodilian. Strikes sideways through water like a needle.",
        sprite_fallback="baby_gecko", is_starter=False,
    ),
    "anaconda": Species(
        id="anaconda", display_name="Green Anaconda", kind="reptile",
        base_hp=58, base_atk=28, base_def=26, base_spd=14, base_luck=15,
        blurb="The world's heaviest snake. Coils once and the conversation is over.",
        sprite_fallback="baby_gecko", is_starter=False,
    ),
    "gila_monster": Species(
        id="gila_monster", display_name="Gila Monster", kind="reptile",
        base_hp=24, base_atk=14, base_def=18, base_spd=8, base_luck=14,
        blurb="A beaded venomous lizard from the desert. Slow but its bite holds on.",
        sprite_fallback="baby_gecko", is_starter=False,
    ),

    # amphibians
    "pacman_frog": Species(
        id="pacman_frog", display_name="Pacman Frog", kind="amphibian",
        base_hp=28, base_atk=18, base_def=14, base_spd=8, base_luck=14,
        blurb="A horned ambush frog the size of a softball. Will try to swallow your finger.",
        sprite_fallback="froglet", is_starter=False,
    ),
    "amphiuma": Species(
        id="amphiuma", display_name="Amphiuma", kind="amphibian",
        base_hp=26, base_atk=12, base_def=18, base_spd=10, base_luck=13,
        blurb="A two-foot eel-shaped salamander with vestigial limbs. Slow, then suddenly not.",
        sprite_fallback="newt", is_starter=False,
    ),
    "purple_frog": Species(
        id="purple_frog", display_name="Purple Frog", kind="amphibian",
        base_hp=32, base_atk=14, base_def=22, base_spd=10, base_luck=15,
        blurb="A pig-snouted burrowing frog from India. Spends most of its life underground.",
        sprite_fallback="froglet", is_starter=False,
    ),
    # ─── Phase 4 chain extensions: tier 6-9 real species ──────────────
    "rhinoceros_iguana": Species(
        id="rhinoceros_iguana", display_name="Rhinoceros Iguana", kind="reptile",
        base_hp=32, base_atk=16, base_def=26, base_spd=12, base_luck=14,
        blurb="A bull-like Caribbean lizard with three small horns and a slow temper.",
        evolutions=(Evolution("caiman_lizard", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="anole", is_starter=False,
    ),
    "caiman_lizard": Species(
        id="caiman_lizard", display_name="Caiman Lizard", kind="reptile",
        base_hp=36, base_atk=20, base_def=28, base_spd=14, base_luck=14,
        blurb="A crocodile-scaled tree lizard from the Amazon. Crushes snail shells whole.",
        evolutions=(Evolution("marine_iguana", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="anole", is_starter=False,
    ),
    "marine_iguana": Species(
        id="marine_iguana", display_name="Marine Iguana", kind="reptile",
        base_hp=40, base_atk=18, base_def=30, base_spd=16, base_luck=15,
        blurb="The only ocean-going lizard. Sneezes salt and dives ten meters for algae.",
        evolutions=(Evolution("galapagos_land_iguana", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="anole", is_starter=False,
    ),
    "galapagos_land_iguana": Species(
        id="galapagos_land_iguana", display_name="Galapagos Land Iguana", kind="reptile",
        base_hp=46, base_atk=22, base_def=32, base_spd=14, base_luck=16,
        blurb="A four-foot golden iguana that lives a hundred years on a windswept island.",
        sprite_fallback="anole", is_starter=False,
    ),
    "andrias_scheuchzeri": Species(
        id="andrias_scheuchzeri", display_name="Andrias Scheuchzeri", kind="amphibian",
        base_hp=38, base_atk=18, base_def=28, base_spd=8, base_luck=14,
        blurb="A real extinct giant salamander. Its skeleton was once mistaken for a drowned man.",
        evolutions=(Evolution("metoposaurus", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="axolotl", is_starter=False,
    ),
    "metoposaurus": Species(
        id="metoposaurus", display_name="Metoposaurus", kind="amphibian",
        base_hp=44, base_atk=22, base_def=30, base_spd=9, base_luck=14,
        blurb="A flat-headed Triassic giant. Lay in shallow water with only its eyes above the surface.",
        evolutions=(Evolution("eryops", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="axolotl", is_starter=False,
    ),
    "eryops": Species(
        id="eryops", display_name="Eryops", kind="amphibian",
        base_hp=50, base_atk=26, base_def=32, base_spd=10, base_luck=15,
        blurb="A Permian apex amphibian with a blunt skull and crushing jaws.",
        evolutions=(Evolution("cacops", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="axolotl", is_starter=False,
    ),
    "cacops": Species(
        id="cacops", display_name="Cacops", kind="amphibian",
        base_hp=56, base_atk=28, base_def=36, base_spd=11, base_luck=16,
        blurb="An armored amphibian with a row of bony plates down its spine. Survived a long time.",
        sprite_fallback="axolotl", is_starter=False,
    ),
    "madagascar_day_gecko": Species(
        id="madagascar_day_gecko", display_name="Madagascar Day Gecko", kind="reptile",
        base_hp=30, base_atk=14, base_def=22, base_spd=18, base_luck=15,
        blurb="A jewel-bright climbing gecko with eyes like beads of green glass.",
        evolutions=(Evolution("tokay_giant", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="baby_gecko", is_starter=False,
    ),
    "tokay_giant": Species(
        id="tokay_giant", display_name="Giant Tokay Gecko", kind="reptile",
        base_hp=36, base_atk=18, base_def=24, base_spd=16, base_luck=14,
        blurb="A heavy-bodied tropical gecko with a bite like a dog. Refuses to let go.",
        evolutions=(Evolution("kawekaweau", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="baby_gecko", is_starter=False,
    ),
    "kawekaweau": Species(
        id="kawekaweau", display_name="Kawekaweau", kind="reptile",
        base_hp=42, base_atk=20, base_def=28, base_spd=14, base_luck=15,
        blurb="A real extinct New Zealand giant gecko, two feet long. Last seen in the 1800s.",
        evolutions=(Evolution("delcourts_giant_gecko", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="baby_gecko", is_starter=False,
    ),
    "delcourts_giant_gecko": Species(
        id="delcourts_giant_gecko", display_name="Delcourt's Giant Gecko", kind="reptile",
        base_hp=50, base_atk=22, base_def=32, base_spd=12, base_luck=16,
        blurb="The largest gecko ever known. Only one specimen exists, in a Marseilles museum.",
        sprite_fallback="baby_gecko", is_starter=False,
    ),
    "surinam_horned_frog": Species(
        id="surinam_horned_frog", display_name="Surinam Horned Frog", kind="amphibian",
        base_hp=32, base_atk=16, base_def=22, base_spd=8, base_luck=16,
        blurb="A round Amazonian ambusher. Will try to swallow anything it can fit its mouth around.",
        evolutions=(Evolution("african_bullfrog", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="froglet", is_starter=False,
    ),
    "african_bullfrog": Species(
        id="african_bullfrog", display_name="African Bullfrog", kind="amphibian",
        base_hp=40, base_atk=20, base_def=26, base_spd=10, base_luck=16,
        blurb="A two-pound frog that bites. Lives 35 years and digs deep against drought.",
        evolutions=(Evolution("titicaca_water_frog", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="froglet", is_starter=False,
    ),
    "titicaca_water_frog": Species(
        id="titicaca_water_frog", display_name="Titicaca Water Frog", kind="amphibian",
        base_hp=46, base_atk=18, base_def=30, base_spd=12, base_luck=17,
        blurb="A wrinkled high-altitude frog that breathes through folds of saggy skin.",
        evolutions=(Evolution("triadobatrachus", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="froglet", is_starter=False,
    ),
    "triadobatrachus": Species(
        id="triadobatrachus", display_name="Triadobatrachus", kind="amphibian",
        base_hp=52, base_atk=20, base_def=32, base_spd=14, base_luck=18,
        blurb="A real Triassic proto-frog — the earliest known frog ancestor. Half tail, half hop.",
        sprite_fallback="froglet", is_starter=False,
    ),
    "myrmecia_bull_ant": Species(
        id="myrmecia_bull_ant", display_name="Myrmecia Bull Ant", kind="insect",
        base_hp=36, base_atk=24, base_def=18, base_spd=22, base_luck=14,
        blurb="An Australian bull ant the size of a thumb. Stings hard enough to remember.",
        evolutions=(Evolution("cariridris", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="ant", is_starter=False,
    ),
    "cariridris": Species(
        id="cariridris", display_name="Cariridris", kind="insect",
        base_hp=42, base_atk=26, base_def=22, base_spd=20, base_luck=14,
        blurb="A real fossil ant from Brazil. One of the earliest known true ants.",
        evolutions=(Evolution("formicium_giganteum", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="ant", is_starter=False,
    ),
    "formicium_giganteum": Species(
        id="formicium_giganteum", display_name="Formicium Giganteum", kind="insect",
        base_hp=50, base_atk=30, base_def=26, base_spd=18, base_luck=15,
        blurb="A real extinct giant ant. Workers were the size of hummingbirds, queens larger still.",
        sprite_fallback="ant", is_starter=False,
    ),
    "brazilian_wandering_spider": Species(
        id="brazilian_wandering_spider", display_name="Brazilian Wandering Spider", kind="insect",
        base_hp=38, base_atk=28, base_def=18, base_spd=18, base_luck=14,
        blurb="An Amazonian hunter that doesn't web — it walks. The most venomous spider alive.",
        evolutions=(Evolution("giant_huntsman_spider", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="bee", is_starter=False,
    ),
    "giant_huntsman_spider": Species(
        id="giant_huntsman_spider", display_name="Giant Huntsman Spider", kind="insect",
        base_hp=44, base_atk=28, base_def=22, base_spd=22, base_luck=14,
        blurb="The largest spider in the world by leg span. A foot across, fast as a thought.",
        evolutions=(Evolution("megarachne", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="bee", is_starter=False,
    ),
    "megarachne": Species(
        id="megarachne", display_name="Megarachne", kind="insect",
        base_hp=52, base_atk=32, base_def=26, base_spd=20, base_luck=15,
        blurb="A real extinct sea-floor arachnid the size of a dinner plate. Long thought to be a spider.",
        sprite_fallback="bee", is_starter=False,
    ),
    "sclerocephalus": Species(
        id="sclerocephalus", display_name="Sclerocephalus", kind="amphibian",
        base_hp=38, base_atk=22, base_def=24, base_spd=8, base_luck=14,
        blurb="A real Permian giant salamander relative. Hunted in shallow lakes alongside early reptiles.",
        evolutions=(Evolution("australerpeton", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="newt", is_starter=False,
    ),
    "australerpeton": Species(
        id="australerpeton", display_name="Australerpeton", kind="amphibian",
        base_hp=44, base_atk=24, base_def=28, base_spd=9, base_luck=14,
        blurb="A real extinct long-snouted amphibian from Brazil. Crocodile-shaped before crocodiles existed.",
        evolutions=(Evolution("platyhystrix", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="newt", is_starter=False,
    ),
    "platyhystrix": Species(
        id="platyhystrix", display_name="Platyhystrix", kind="amphibian",
        base_hp=50, base_atk=26, base_def=32, base_spd=10, base_luck=15,
        blurb="A real Permian amphibian with a tall sail on its back. Built like a small reptilian dimetrodon.",
        sprite_fallback="newt", is_starter=False,
    ),
    "cave_lion": Species(
        id="cave_lion", display_name="Cave Lion", kind="beast",
        base_hp=50, base_atk=36, base_def=24, base_spd=22, base_luck=14,
        blurb="A real extinct lion that hunted Pleistocene Europe. Larger than any modern lion.",
        evolutions=(Evolution("american_lion", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="hare", is_starter=False,
    ),
    "american_lion": Species(
        id="american_lion", display_name="American Lion", kind="beast",
        base_hp=58, base_atk=40, base_def=26, base_spd=20, base_luck=15,
        blurb="A real extinct lion from Ice Age North America. The largest cat that ever lived.",
        evolutions=(Evolution("homotherium", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="hare", is_starter=False,
    ),
    "homotherium": Species(
        id="homotherium", display_name="Homotherium", kind="beast",
        base_hp=64, base_atk=42, base_def=28, base_spd=24, base_luck=16,
        blurb="A real extinct scimitar-toothed cat. Long legs, short fangs, ran prey to exhaustion.",
        sprite_fallback="hare", is_starter=False,
    ),
    "mongolarachne": Species(
        id="mongolarachne", display_name="Mongolarachne", kind="insect",
        base_hp=44, base_atk=26, base_def=28, base_spd=16, base_luck=15,
        blurb="A real Jurassic spider with a foot-wide leg span. The largest fossil spider known.",
        evolutions=(Evolution("pneumodesmus", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="ladybug", is_starter=False,
    ),
    "pneumodesmus": Species(
        id="pneumodesmus", display_name="Pneumodesmus", kind="insect",
        base_hp=52, base_atk=28, base_def=32, base_spd=14, base_luck=16,
        blurb="A real Silurian millipede — the oldest land animal ever found. Tiny but ancient.",
        sprite_fallback="ladybug", is_starter=False,
    ),
    "bullockornis": Species(
        id="bullockornis", display_name="Bullockornis", kind="avian",
        base_hp=48, base_atk=28, base_def=32, base_spd=14, base_luck=15,
        blurb="A real extinct giant bird from Australia, nicknamed the 'demon duck of doom'.",
        evolutions=(Evolution("dromornis", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="chick", is_starter=False,
    ),
    "dromornis": Species(
        id="dromornis", display_name="Dromornis", kind="avian",
        base_hp=56, base_atk=32, base_def=36, base_spd=12, base_luck=16,
        blurb="A real extinct mihirung bird from Australia. Half a ton of flightless menace.",
        sprite_fallback="chick", is_starter=False,
    ),
    "osteodontornis": Species(
        id="osteodontornis", display_name="Osteodontornis", kind="avian",
        base_hp=44, base_atk=28, base_def=24, base_spd=28, base_luck=16,
        blurb="A real extinct toothed seabird. Twenty-foot wingspan, soaring miles above the waves.",
        evolutions=(Evolution("gigantornis", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="duckling", is_starter=False,
    ),
    "gigantornis": Species(
        id="gigantornis", display_name="Gigantornis", kind="avian",
        base_hp=52, base_atk=32, base_def=26, base_spd=30, base_luck=17,
        blurb="A real extinct Eocene seabird, possibly the largest flying seabird that ever lived.",
        sprite_fallback="duckling", is_starter=False,
    ),
    "castoroides": Species(
        id="castoroides", display_name="Castoroides", kind="beast",
        base_hp=56, base_atk=22, base_def=38, base_spd=12, base_luck=14,
        blurb="A real extinct giant beaver. Two and a half meters long, weighed as much as a person.",
        evolutions=(Evolution("procoptodon", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="field_mouse", is_starter=False,
    ),
    "procoptodon": Species(
        id="procoptodon", display_name="Procoptodon", kind="beast",
        base_hp=62, base_atk=26, base_def=40, base_spd=18, base_luck=15,
        blurb="A real extinct short-faced kangaroo. Two meters tall, hopped Pleistocene Australia.",
        sprite_fallback="field_mouse", is_starter=False,
    ),
    "helicoprion": Species(
        id="helicoprion", display_name="Helicoprion", kind="aquatic",
        base_hp=50, base_atk=38, base_def=28, base_spd=26, base_luck=15,
        blurb="A real extinct shark with a buzzsaw of teeth in its lower jaw. Looked impossible.",
        evolutions=(Evolution("cretoxyrhina", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="guppy", is_starter=False,
    ),
    "cretoxyrhina": Species(
        id="cretoxyrhina", display_name="Cretoxyrhina", kind="aquatic",
        base_hp=58, base_atk=42, base_def=30, base_spd=28, base_luck=16,
        blurb="A real extinct 'ginsu shark' from the Cretaceous. Carved through sea reptiles.",
        sprite_fallback="guppy", is_starter=False,
    ),
    "protostega": Species(
        id="protostega", display_name="Protostega", kind="reptile",
        base_hp=54, base_atk=24, base_def=40, base_spd=12, base_luck=14,
        blurb="A real extinct sea turtle with a paddle-armed body and a shell six feet across.",
        evolutions=(Evolution("puentemys", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="hatchling_turtle", is_starter=False,
    ),
    "puentemys": Species(
        id="puentemys", display_name="Puentemys", kind="reptile",
        base_hp=60, base_atk=26, base_def=44, base_spd=10, base_luck=15,
        blurb="A real extinct Paleocene side-necked turtle. Eight feet wide, shaped like a coin.",
        sprite_fallback="hatchling_turtle", is_starter=False,
    ),
    "eremotherium": Species(
        id="eremotherium", display_name="Eremotherium", kind="beast",
        base_hp=64, base_atk=30, base_def=42, base_spd=10, base_luck=14,
        blurb="A real extinct giant ground sloth. Stood twenty feet tall reaching for treetops.",
        evolutions=(Evolution("arctotherium", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="hedgehog", is_starter=False,
    ),
    "arctotherium": Species(
        id="arctotherium", display_name="Arctotherium", kind="beast",
        base_hp=72, base_atk=36, base_def=44, base_spd=12, base_luck=15,
        blurb="A real extinct South American short-faced bear. The largest bear that ever lived.",
        sprite_fallback="hedgehog", is_starter=False,
    ),
    "titanichthys": Species(
        id="titanichthys", display_name="Titanichthys", kind="aquatic",
        base_hp=58, base_atk=30, base_def=36, base_spd=14, base_luck=14,
        blurb="A real extinct giant placoderm. Filter-fed like a whale shark with armor plates.",
        evolutions=(Evolution("xiphactinus", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="minnow", is_starter=False,
    ),
    "xiphactinus": Species(
        id="xiphactinus", display_name="Xiphactinus", kind="aquatic",
        base_hp=66, base_atk=38, base_def=32, base_spd=22, base_luck=15,
        blurb="A real extinct Cretaceous predatory fish. Thirteen feet long with a mouth full of fangs.",
        sprite_fallback="minnow", is_starter=False,
    ),
    "thylacosmilus": Species(
        id="thylacosmilus", display_name="Thylacosmilus", kind="beast",
        base_hp=56, base_atk=38, base_def=22, base_spd=24, base_luck=14,
        blurb="A real extinct South American sabertooth, but a marsupial. Convergent evolution at work.",
        evolutions=(Evolution("machairodus", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="hare", is_starter=False,
    ),
    "machairodus": Species(
        id="machairodus", display_name="Machairodus", kind="beast",
        base_hp=64, base_atk=42, base_def=24, base_spd=26, base_luck=15,
        blurb="A real extinct sabertooth cat genus. Cousin of smilodon, leaner and longer-legged.",
        sprite_fallback="hare", is_starter=False,
    ),
    "prognathodon": Species(
        id="prognathodon", display_name="Prognathodon", kind="reptile",
        base_hp=60, base_atk=36, base_def=30, base_spd=24, base_luck=14,
        blurb="A real extinct mosasaur with a deep skull and crushing teeth. Bit through ammonites.",
        evolutions=(Evolution("kronosaurus", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="skink", is_starter=False,
    ),
    "kronosaurus": Species(
        id="kronosaurus", display_name="Kronosaurus", kind="reptile",
        base_hp=70, base_atk=42, base_def=32, base_spd=22, base_luck=15,
        blurb="A real extinct giant pliosaur. Forty feet long, named for the titan that ate his children.",
        sprite_fallback="skink", is_starter=False,
    ),
    "kelenken": Species(
        id="kelenken", display_name="Kelenken", kind="avian",
        base_hp=58, base_atk=34, base_def=28, base_spd=26, base_luck=15,
        blurb="A real extinct terror bird. Largest skull of any known bird, ever.",
        evolutions=(Evolution("titanis_walleri", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="sparrow", is_starter=False,
    ),
    "titanis_walleri": Species(
        id="titanis_walleri", display_name="Titanis Walleri", kind="avian",
        base_hp=64, base_atk=38, base_def=30, base_spd=28, base_luck=16,
        blurb="A real extinct North American terror bird. Crossed the Panama land bridge to hunt.",
        sprite_fallback="sparrow", is_starter=False,
    ),
    "lethiscus": Species(
        id="lethiscus", display_name="Lethiscus", kind="amphibian",
        base_hp=50, base_atk=24, base_def=32, base_spd=12, base_luck=14,
        blurb="A real extinct early limbless amphibian, found in Scotland. Like a small ancient eel.",
        evolutions=(Evolution("diplocaulus", requirements={"hp": 28}, stat_bonus=_TIER_5_BONUS),),
        sprite_fallback="tadpole", is_starter=False,
    ),
    "diplocaulus": Species(
        id="diplocaulus", display_name="Diplocaulus", kind="amphibian",
        base_hp=56, base_atk=26, base_def=36, base_spd=14, base_luck=15,
        blurb="A real Permian amphibian with a boomerang-shaped head. Looks made-up but isn't.",
        sprite_fallback="tadpole", is_starter=False,
    ),
    "pterygotus": Species(
        id="pterygotus", display_name="Pterygotus", kind="aquatic",
        base_hp=60, base_atk=32, base_def=36, base_spd=18, base_luck=15,
        blurb="A real extinct giant sea scorpion. Six feet long with grasping pincers.",
        sprite_fallback="shrimp", is_starter=False,
    ),
    "tusoteuthis": Species(
        id="tusoteuthis", display_name="Tusoteuthis", kind="aquatic",
        base_hp=64, base_atk=32, base_def=38, base_spd=22, base_luck=16,
        blurb="A real extinct Cretaceous giant squid. Estimated at thirty feet, hunted by mosasaurs.",
        sprite_fallback="snail", is_starter=False,
    ),
    "argentavis_apex": Species(
        id="argentavis_apex", display_name="Argentavis Imperator", kind="avian",
        base_hp=56, base_atk=38, base_def=26, base_spd=30, base_luck=16,
        blurb="A real extinct giant teratorn — twenty-foot wingspan, the largest flying bird ever.",
        sprite_fallback="wren", is_starter=False,
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
    attack_frames: list[list[str]] = field(default_factory=list)
    hurt_frames: list[list[str]] = field(default_factory=list)


_SPRITE_CACHE: dict[str, Sprite] = {}
_SHARED_QUEST_CACHE: Optional[list[list[str]]] = None


def _parse_sprite_file(text: str) -> Sprite:
    """Parse a sprite .txt file into idle / quest / attack / hurt frame banks.

    Frames inside each bank are delimited by a line containing only
    `--FRAME--`. Bank-switch markers (each on its own line) shift
    subsequent frames into a new bank: `--QUEST--`, `--ATTACK--`, `--HURT--`.
    Leading/trailing blank lines on each frame are trimmed.
    """
    idle: list[list[str]] = []
    quest: list[list[str]] = []
    attack: list[list[str]] = []
    hurt: list[list[str]] = []
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
        if marker == "--ATTACK--":
            if buf:
                current_bank.append(buf)
                buf = []
            current_bank = attack
            continue
        if marker == "--HURT--":
            if buf:
                current_bank.append(buf)
                buf = []
            current_bank = hurt
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
        attack_frames=[f for f in (_trim(f) for f in attack) if f],
        hurt_frames=[f for f in (_trim(f) for f in hurt) if f],
    )


def _load_sprite(species_id: str) -> Sprite:
    if species_id in _SPRITE_CACHE:
        return _SPRITE_CACHE[species_id]
    path = paths.sprites_dir() / f"{species_id}.txt"
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


def attack_frames(species_id: str) -> list[list[str]]:
    """Return the species's --ATTACK-- bank, or empty list if absent."""
    return _load_sprite(species_id).attack_frames


def hurt_frames(species_id: str) -> list[list[str]]:
    """Return the species's --HURT-- bank, or empty list if absent."""
    return _load_sprite(species_id).hurt_frames


def quest_sprite_frames() -> list[list[str]]:
    """Return the shared 'away on quest' frames, or an empty list if the
    shared sprite file is missing. Callers should fall back to species idle
    frames when this returns an empty list.
    """
    global _SHARED_QUEST_CACHE
    if _SHARED_QUEST_CACHE is not None:
        return _SHARED_QUEST_CACHE
    path = paths.sprites_dir() / "_quest.txt"
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
