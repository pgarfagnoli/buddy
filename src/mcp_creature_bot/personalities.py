"""Named personalities — the discrete label layer on top of behavior traits.

A `Personality` is a Pokemon-nature-style preset: one stable name that
pins curiosity/boldness/patience to a canonical trait vector. New
buddies roll a personality weighted by species affinity and inherit
its trait values directly. Legacy buddies whose saves predate this
module are backfilled via `closest_to_traits` in state deserialization.
"""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Personality:
    id: str
    display_name: str
    blurb: str
    traits: dict[str, int]  # keys: curiosity, boldness, patience — 0-10 each


PERSONALITIES: dict[str, Personality] = {
    "brave":       Personality("brave",       "Brave",       "Charges in first, thinks later.",        {"curiosity": 5, "boldness": 9, "patience": 4}),
    "curious":     Personality("curious",     "Curious",     "Pokes at everything that moves.",        {"curiosity": 9, "boldness": 5, "patience": 4}),
    "stoic":       Personality("stoic",       "Stoic",       "Stolid and enduring. Hard to rattle.",   {"curiosity": 3, "boldness": 6, "patience": 9}),
    "playful":     Personality("playful",     "Playful",     "Chases its own shadow for fun.",         {"curiosity": 8, "boldness": 7, "patience": 3}),
    "cautious":    Personality("cautious",    "Cautious",    "Watches a problem before touching it.",  {"curiosity": 4, "boldness": 3, "patience": 8}),
    "diligent":    Personality("diligent",    "Diligent",    "Quiet, persistent, always working.",     {"curiosity": 5, "boldness": 5, "patience": 8}),
    "timid":       Personality("timid",       "Timid",       "Prefers hiding spots to open ground.",   {"curiosity": 5, "boldness": 2, "patience": 6}),
    "mischievous": Personality("mischievous", "Mischievous", "Knocks things over for science.",        {"curiosity": 7, "boldness": 7, "patience": 3}),
    "dreamy":      Personality("dreamy",      "Dreamy",      "Gets distracted by clouds. Often.",      {"curiosity": 6, "boldness": 3, "patience": 7}),
    "restless":    Personality("restless",    "Restless",    "Can never sit still for long.",          {"curiosity": 7, "boldness": 6, "patience": 2}),
    "balanced":    Personality("balanced",    "Balanced",    "No strong tendencies either way.",       {"curiosity": 5, "boldness": 5, "patience": 5}),
}


SPECIES_PERSONALITY_BIAS: dict[str, tuple[str, ...]] = {
    "ant":         ("diligent", "stoic", "cautious"),
    "bee":         ("brave", "playful", "mischievous", "restless"),
    "rabbit":      ("timid", "curious", "restless"),
    "field_mouse": ("curious", "cautious", "timid"),
    "squirrel":    ("playful", "curious", "restless"),
    "ladybug":     ("dreamy", "diligent"),
    "frog":        ("dreamy", "stoic"),
    "newt":        ("cautious", "dreamy"),
    "wren":        ("brave", "curious", "restless"),
    "minnow":      ("timid", "restless"),
}


_BASE_WEIGHT = 1
_BIAS_WEIGHT = 3


def roll_for_species(species_id: str, rng: random.Random) -> Personality:
    """Weighted random pick. Every personality starts at baseline weight 1;
    any listed in `SPECIES_PERSONALITY_BIAS[species_id]` gets +3 on top.

    The injected rng makes tests deterministic.
    """
    preferred = set(SPECIES_PERSONALITY_BIAS.get(species_id, ()))
    ids = list(PERSONALITIES.keys())
    weights = [
        _BASE_WEIGHT + (_BIAS_WEIGHT if pid in preferred else 0)
        for pid in ids
    ]
    pid = rng.choices(ids, weights=weights, k=1)[0]
    return PERSONALITIES[pid]


def closest_to_traits(traits: dict[str, int]) -> Personality:
    """Return the catalogue personality whose canonical trait vector is
    nearest (squared Euclidean) to the given dict.

    Missing keys default to 5. Used by the legacy-save backfill path —
    we describe what's already there rather than overwriting it.
    """
    c = int(traits.get("curiosity", 5))
    b = int(traits.get("boldness", 5))
    p = int(traits.get("patience", 5))
    best: Personality = PERSONALITIES["balanced"]
    best_d = None
    for cand in PERSONALITIES.values():
        tc = cand.traits.get("curiosity", 5)
        tb = cand.traits.get("boldness", 5)
        tp = cand.traits.get("patience", 5)
        d = (c - tc) ** 2 + (b - tb) ** 2 + (p - tp) ** 2
        if best_d is None or d < best_d:
            best_d = d
            best = cand
    return best
