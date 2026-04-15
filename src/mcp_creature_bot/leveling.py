"""XP, level curve, and level-up logic."""
from __future__ import annotations

import time
from typing import Optional

from . import skills, species
from .state import Buddy, State


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


def xp_to_next(level: int, tier: int = 0) -> int:
    """XP needed to go from `level` to `level+1`.

    The curve grows with both level and evolution tier. Higher-tier species
    need more XP per level than starters at the same level — a tier-4 apex
    form needs 3x as much XP as a tier-0 starter. This makes reaching the
    top of a deep lineage a real commitment while keeping starter pacing
    unchanged.
    """
    return round(50 * (level ** 1.5) * (1 + tier * 0.5))


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


def _try_evolve(state: State) -> Optional[str]:
    """If the buddy just hit its species' evolves_at level and has
    evolutions available, pick the branch whose match_stats contains the
    current dominant stat (default to the first branch), apply its flat
    stat bonus, swap the species id, and full-heal. Returns the log line
    if an evolution happened, else None.
    """
    b = state.buddy
    if b is None:
        return None
    current = species.get(b.species)
    if current.evolves_at is None or b.level != current.evolves_at:
        return None
    if not current.evolutions:
        return None
    dominant = species.get_dominant_stat(b.stats)
    chosen = next(
        (e for e in current.evolutions if dominant in e.match_stats),
        current.evolutions[0],
    )
    new_sp = species.get(chosen.evolved_species_id)
    old_name = current.display_name
    b.species = new_sp.id
    for stat_key, delta in chosen.stat_bonus.items():
        setattr(b.stats, stat_key, getattr(b.stats, stat_key) + delta)
    b.current_hp = b.stats.hp  # full heal on evolution
    b.current_mana = b.max_mana
    b.level = 1                # reset to Lv1 for the new form
    b.xp = 0                   # clean slate; surplus XP from the triggering level-up is discarded
    line = f"{b.name} evolved from {old_name} into {new_sp.display_name}!"
    state.add_event(line)
    newly: list[str] = []
    if chosen.grants_skill and skills._learn(b, chosen.grants_skill):
        newly.append(chosen.grants_skill)
    newly.extend(skills.check_and_grant_skills(b))
    _announce_new_skills(state, b, newly)
    return line


def check_level_ups(state: State) -> list[str]:
    """Apply as many level-ups as the buddy's current xp warrants. Returns log lines."""
    messages: list[str] = []
    if state.buddy is None:
        return messages
    b = state.buddy
    while b.xp >= xp_to_next(b.level, species.get_tier(b.species)):
        b.xp -= xp_to_next(b.level, species.get_tier(b.species))
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
        evo_msg = _try_evolve(state)
        if evo_msg:
            messages.append(evo_msg)
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
