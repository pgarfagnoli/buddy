"""XP, level curve, and level-up logic."""
from __future__ import annotations

import time
from typing import Optional

import skills, species
from state import Buddy, State


def _announce_new_skills(state: State, buddy: Buddy, newly: list[str]) -> None:
    for sid in newly:
        try:
            s = skills.get(sid)
            line = f"{buddy.name} learned {s.name}!"
        except KeyError:
            line = f"{buddy.name} learned {sid}!"
        state.add_event(line)


XP_TOKEN_BONUS_CAP = 20  # cap on input + cache_creation bonus
STREAK_WINDOW_S = 30 * 60
STREAK_BONUS = 5
STAT_POINTS_PER_LEVEL = 3
MAX_HP_PER_LEVEL = 5
MANA_REGEN_PER_PROMPT = 2


def xp_to_next(level: int, tier: int = 0, evolves_at: Optional[int] = None) -> int:
    """XP needed to go from `level` to `level+1`.

    The base curve grows with level and evolution tier — a tier-4 apex form
    needs 3x as much XP as a tier-0 starter at the same level. On top of
    that, leveling past the species's `evolves_at` is soft-capped: each
    level at-or-past the threshold multiplies the cost by 3^(excess+1),
    making it prohibitive to drift past the evolve level without actually
    evolving. The cap is naturally self-limiting; the level-up loop stops
    on its own once the cost outruns realistic XP gain.
    """
    base = round(50 * (level ** 1.5) * (1 + tier * 0.5))
    if evolves_at is not None and level >= evolves_at:
        excess = level - evolves_at + 1  # 1 at the evolve level itself
        return base * (3 ** excess)
    return base


def xp_for_tokens(
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int,
    last_prompt_at: int,
    now: int,
) -> int:
    base = max(1, output_tokens // 250)
    bonus = min(input_tokens // 2500 + cache_creation_tokens // 2500, XP_TOKEN_BONUS_CAP)
    xp = base + bonus
    if last_prompt_at and (now - last_prompt_at) < STREAK_WINDOW_S:
        xp += STREAK_BONUS
    return xp


def check_level_ups(state: State) -> list[str]:
    """Apply as many level-ups as the buddy's current xp warrants. Returns log lines."""
    messages: list[str] = []
    if state.buddy is None:
        return messages
    b = state.buddy
    while True:
        sp = species.get(b.species)
        cost = xp_to_next(b.level, species.get_tier(b.species), sp.evolves_at)
        if b.xp < cost:
            break
        b.xp -= cost
        b.level += 1
        b.stats.hp += MAX_HP_PER_LEVEL
        b.stat_points_unspent += STAT_POINTS_PER_LEVEL
        b.current_hp = b.stats.hp
        b.current_mana = b.max_mana
        msg = f"{b.name} leveled up! Now Lv{b.level} (+{STAT_POINTS_PER_LEVEL} stat points)"
        messages.append(msg)
        state.add_event(msg)
        newly = skills.check_and_grant_skills(b)
        _announce_new_skills(state, b, newly)
    return messages


def apply_xp_events(state: State, events: list[dict]) -> list[str]:
    """Mutate state with XP events. Returns human-readable log lines of level-ups."""
    if state.buddy is None or not events:
        return []
    b = state.buddy
    for ev in events:
        t = int(ev.get("t", time.time()))
        ti = int(ev.get("input_tokens", 0))
        to = int(ev.get("output_tokens", 0))
        tc = int(ev.get("cache_creation_tokens", 0))
        if not (ti or to or tc) and "prompt_len" in ev:
            to = int(ev["prompt_len"])
        b.xp += xp_for_tokens(ti, to, tc, b.last_prompt_at, t)
        b.current_mana = min(b.max_mana, b.current_mana + MANA_REGEN_PER_PROMPT)
        b.last_prompt_at = t
        b.prompts_count += 1
    return check_level_ups(state)
