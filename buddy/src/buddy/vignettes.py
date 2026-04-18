"""Instant ambient flavor moments for the idle activity loop.

A Vignette is a zero-duration event: no XP, no item, no stat check.
It renders as a single line in `state.recent_events` and lets the
buddy feel alive between quests. The activity loop uses `pick()` as
the fallback when `claude -p` isn't available — the LLM path can also
return a `Vignette.text` when it chooses the `idle_flavor` action.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import random as _random_mod

    from .state import Buddy


@dataclass(frozen=True)
class Vignette:
    id: str
    text: str  # contains "{name}" — format with buddy name before emitting
    moods: tuple[str, ...]  # e.g. ("patient", "lazy") — matched against traits


VIGNETTES: tuple[Vignette, ...] = (
    Vignette("cloud_watch",  "{name} lies on its back and watches the clouds drift by", ("patient", "lazy")),
    Vignette("dew_admire",   "{name} pokes a dewdrop and watches it shimmer",            ("curious",)),
    Vignette("leaf_chase",   "{name} chases a falling leaf in a slow circle",            ("curious", "mischief")),
    Vignette("stretch",      "{name} stretches until its joints pop",                    ("lazy",)),
    Vignette("warm_rock",    "{name} presses itself to a sun-warm rock and sighs",       ("lazy", "patient")),
    Vignette("shadow_dance", "{name} hops in and out of its own shadow",                 ("mischief",)),
    Vignette("pebble_sort",  "{name} lines up three pebbles by size, very seriously",    ("patient", "curious")),
    Vignette("ear_flick",    "{name} flicks at an imaginary fly",                        ()),
    Vignette("tail_chase",   "{name} chases its own tail, stops, looks embarrassed",     ("mischief",)),
    Vignette("sniff_flower", "{name} sniffs a wildflower and sneezes politely",          ("curious",)),
    Vignette("hum_to_self",  "{name} hums a tune only it can remember",                  ("patient",)),
    Vignette("puff_chest",   "{name} puffs its chest at a passing butterfly",            ("bold",)),
    Vignette("stare_moss",   "{name} stares at a patch of moss and contemplates life",   ("patient",)),
    Vignette("spin_once",    "{name} spins in place once, for no reason",                ("mischief",)),
    Vignette("rummage",      "{name} rummages in its own inventory pouch",               ("curious",)),
    Vignette("count_toes",   "{name} counts its toes, loses count, starts again",        ("patient",)),
    Vignette("doze_off",     "{name} dozes off mid-thought and snores faintly",          ("lazy",)),
    Vignette("twig_balance", "{name} balances a twig on its nose for three full seconds", ("patient", "mischief")),
    Vignette("acorn_kick",   "{name} kicks a stray acorn and pretends it was on purpose", ("mischief",)),
    Vignette("yawn_wide",    "{name} yawns so wide its whole face creases",              ("lazy",)),
    Vignette("study_ant",    "{name} studies an ant convoy with great seriousness",      ("curious", "patient")),
    Vignette("howl_practice", "{name} practices a tiny howl and is satisfied",           ("bold",)),
    Vignette("paw_clean",    "{name} cleans one paw with great care, ignores the others", ("patient",)),
    Vignette("breeze_sniff", "{name} sniffs the breeze and decides nothing is happening", ()),
    Vignette("shadow_sneak", "{name} sneaks up on its own shadow and pounces",           ("mischief",)),
    Vignette("rock_tap",     "{name} taps a rock twice, listens, taps once more",        ("curious",)),
    Vignette("chest_thump",  "{name} thumps its chest at no one in particular",          ("bold",)),
    Vignette("circle_thrice", "{name} circles three times before settling on the spot",  ("lazy",)),
    Vignette("button_nose",  "{name} presses its nose to a flower and goes cross-eyed",  ("curious",)),
    Vignette("idle_hum",     "{name} hums a low note and pretends it's a song",          ()),
    Vignette("imagine_hat",  "{name} imagines itself in a tiny hat and approves",        ("mischief",)),
    Vignette("rear_up",      "{name} rears up on its hind legs to look bigger",          ("bold",)),
)


def _trait(buddy: "Buddy", key: str) -> int:
    return int(buddy.traits.get(key, 5))


def _dominant_moods(buddy: "Buddy") -> set[str]:
    """Map the buddy's 0-10 trait dials to loose mood tags.

    A trait above 6 is strong enough to attract matching vignettes; a
    trait below 4 pulls toward its opposite (currently only patience
    has one — low patience → lazy is *not* applied; low patience just
    doesn't get the 'patient'/'lazy' boost).
    """
    moods: set[str] = set()
    if _trait(buddy, "curiosity") >= 6:
        moods.add("curious")
    if _trait(buddy, "boldness") >= 6:
        moods.add("bold")
        moods.add("mischief")
    if _trait(buddy, "patience") >= 6:
        moods.add("patient")
        moods.add("lazy")
    return moods


def pick(buddy: "Buddy", rng: "_random_mod.Random") -> Vignette:
    """Weighted draw over VIGNETTES. Matching moods get extra weight.

    A vignette with zero mood tags is a universal fallback (weight 1).
    A tagged vignette matching one dominant mood gets weight 3; two
    matches gets weight 5. Untagged-matching vignettes still get their
    baseline weight.
    """
    active = _dominant_moods(buddy)
    weights: list[int] = []
    for v in VIGNETTES:
        if not v.moods:
            weights.append(2)  # mild neutral preference
            continue
        matches = sum(1 for m in v.moods if m in active)
        if matches == 0:
            weights.append(1)
        elif matches == 1:
            weights.append(3)
        else:
            weights.append(5)
    return rng.choices(VIGNETTES, weights=weights, k=1)[0]


def render(vignette: Vignette, buddy: "Buddy") -> str:
    return vignette.text.format(name=buddy.name)
