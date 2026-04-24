"""MCP tool handlers exposed to Claude Code via the plugin's stdio server.

Every tool call starts with drain_xp_log + _sync_apply, which pulls pending
XP events from the hook-writer ring buffer and folds them into the
authoritative state. The tool does its own work inside the same
mutate_state exclusive section so writes can't race.

The previous `src/buddy/server.py` also owned tmux sidecar-pane lifecycle
and an activity-loop singleton; both are gone in the plugin rewrite. Pane
rendering moved to the standalone `buddy-pane` CLI; there's no background
loop anymore.
"""
from __future__ import annotations

import random
import time
from typing import Any

from mini_mcp import FastMCP

import leveling
import personalities
import quests
import skills
import species
from state import (
    Buddy,
    MythicOverlay,
    State,
    Stats,
    _buddy_to_dict,
    drain_xp_log,
    mutate_state,
    read_hook_events,
)

mcp = FastMCP("buddy")


# ─── helpers ────────────────────────────────────────────────────────────────

def _sync_apply(state: State, events: list[dict]) -> list[str]:
    """Apply pending XP events. Returns level-up messages if any."""
    return leveling.apply_xp_events(state, events)


def _require_buddy(state: State) -> Buddy:
    if state.buddy is None:
        raise ValueError("no buddy yet — call choose_buddy first (use list_species to see options)")
    return state.buddy


def _snapshot(state: State) -> dict[str, Any]:
    if state.buddy is None:
        return {
            "buddy": None,
            "recent_events": list(state.recent_events),
        }
    b = state.buddy
    bd = _buddy_to_dict(b)
    bd["max_hp"] = b.max_hp
    bd["max_mana"] = b.max_mana
    bd["xp_to_next"] = leveling.xp_to_next(
        b.level, species.get_tier(b.species), species.get(b.species).evolves_at
    )
    bd["traits"] = dict(b.traits)
    bd["personality_display"] = (
        personalities.PERSONALITIES[b.personality].display_name
        if b.personality in personalities.PERSONALITIES
        else ""
    )
    if b.quest:
        qdef = quests.get(b.quest.id)
        bd["quest"] = {
            **bd["quest"],
            "name": qdef.name,
            "remaining_s": b.quest.remaining(),
            "done": b.quest.is_done(),
        }
    sp = species.get(b.species)
    # A mythic overlay renames the creature but keeps the underlying apex
    # species (for sprite + kind). If present, it wins over the species's
    # own display name / blurb.
    display_name = b.mythic.display_name if b.mythic else sp.display_name
    bd["species_info"] = {"id": sp.id, "display_name": display_name, "kind": sp.kind}
    if b.mythic is not None:
        bd["mythic"] = {
            "display_name": b.mythic.display_name,
            "blurb": b.mythic.blurb,
            "committed_at": b.mythic.committed_at,
            "stat_bonus": dict(b.mythic.stat_bonus),
        }
    if sp.evolves_at is not None and sp.evolutions:
        branches = [species.branch_eligibility(e, b.stats) for e in sp.evolutions]
        bd["evolution_ready"] = {
            "trigger_level": sp.evolves_at,
            "at_or_past_level": b.level >= sp.evolves_at,
            "branches": branches,
            "any_eligible": any(br["eligible"] for br in branches),
        }
    # Post-apex mythic readiness signal: apex species at or above their
    # mythic_at level, not yet ascended. Drives the /buddy dispatcher to
    # prompt Claude to invent a unique legendary form.
    if (
        b.mythic is None
        and sp.mythic_at is not None
        and b.level >= sp.mythic_at
    ):
        bd["mythic_ready"] = {
            "trigger_level": sp.mythic_at,
            "apex_form": sp.display_name,
            "current_stats": {
                "hp": b.stats.hp, "atk": b.stats.atk, "def": b.stats.def_,
                "spd": b.stats.spd, "luck": b.stats.luck,
                "int": b.stats.int_, "res": b.stats.res,
            },
            "recent_events": list(state.recent_events[-5:]),
            "cap_total": 40,
            "cap_per_stat": 15,
        }
    # Pre-formatted display for fast relay by Claude — avoids expensive
    # reasoning over the raw JSON on every /buddy status call.
    lines: list[str] = []
    lines.append(
        f"{b.name} ({display_name} Lv{b.level})  "
        f"HP {b.current_hp}/{b.max_hp}  MP {b.current_mana}/{b.max_mana}  "
        f"XP {b.xp}/{bd['xp_to_next']}"
    )
    s = b.stats
    lines.append(f"ATK {s.atk}  DEF {s.def_}  SPD {s.spd}  LUCK {s.luck}  INT {s.int_}  RES {s.res}")
    if b.stat_points_unspent:
        lines.append(f"{b.stat_points_unspent} unspent stat points")
    if b.quest:
        q = bd["quest"]
        if q["done"]:
            lines.append(f"Quest: {q['name']} — done! Run /buddy claim")
        else:
            lines.append(f"Quest: {q['name']} — {q['remaining_s']}s left")
    else:
        lines.append("Quest: idle")
    if b.active_skills:
        lines.append(f"Skills: {', '.join(b.active_skills)}")
    if state.recent_events:
        for ev in state.recent_events[-3:]:
            lines.append(ev)
    evo = bd.get("evolution_ready")
    if evo:
        if evo["at_or_past_level"] and evo["any_eligible"]:
            names = [br["display_name"] for br in evo["branches"] if br["eligible"]]
            lines.append(f"Evolution ready: {', '.join(names)} — run /buddy evolve")
        elif not evo["at_or_past_level"]:
            lines.append(f"Evolution at Lv{evo['trigger_level']} (current Lv{b.level})")
    bd["display"] = "\n".join(lines)

    return {
        "buddy": bd,
        "recent_events": list(state.recent_events[-5:]),
        "display": bd["display"],
    }


# ─── tools ──────────────────────────────────────────────────────────────────

@mcp.tool()
def get_buddy() -> dict[str, Any]:
    """Get the current buddy's full state: level, xp, stats, quest, recent events.

    Call this first if the user asks about their buddy's status. If the returned
    `buddy` field is null, prompt the user to pick a starter via list_species + choose_buddy.

    Auto-claims any finished quest that the activity loop and pane missed
    (e.g., both processes were dead while the quest timer expired).
    """
    events = drain_xp_log()

    def fn(state: State) -> None:
        _sync_apply(state, events)
        b = state.buddy
        if b is not None and b.quest is not None and b.quest.is_done():
            try:
                result = quests.claim(b)
                fired_names: list[str] = []
                for sid in result.fired_skills:
                    try:
                        fired_names.append(skills.get(sid).name)
                    except KeyError:
                        fired_names.append(sid)
                state.add_event(quests.format_claim_event_line(result, fired_names))
                leveling.check_level_ups(state)
            except ValueError:
                pass  # quest not actually done (race) — ignore

    state = mutate_state(fn)
    return _snapshot(state)


@mcp.tool()
def hook_diagnostics(window_minutes: int = 10) -> dict[str, Any]:
    """Show which Claude Code sessions have fed the buddy recently.

    Returns one entry per session_id seen in the last `window_minutes`, with
    fire count, cwd, total output tokens, and last fire timestamp. Use this
    to verify that every window/tab you expect to be contributing is actually
    firing its Stop hook.
    """
    since = int(time.time()) - max(1, window_minutes) * 60
    events = read_hook_events(since_ts=since)
    by_session: dict[str, dict[str, Any]] = {}
    for ev in events:
        sid = ev.get("session") or "(unknown)"
        row = by_session.get(sid)
        if row is None:
            row = {
                "session": sid,
                "cwd": ev.get("cwd") or "",
                "fires": 0,
                "parse_ok_fires": 0,
                "zero_token_fires": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cache_creation_tokens": 0,
                "first_fire": int(ev.get("t", 0)),
                "last_fire": int(ev.get("t", 0)),
            }
            by_session[sid] = row
        row["fires"] += 1
        out_tok = int(ev.get("output_tokens") or 0)
        # Legacy events may not have `parse_ok`; infer from output_tokens.
        parse_ok = ev.get("parse_ok")
        if parse_ok is None:
            parse_ok = out_tok > 0
        if parse_ok:
            row["parse_ok_fires"] += 1
        if out_tok == 0:
            row["zero_token_fires"] += 1
        row["total_input_tokens"] += int(ev.get("input_tokens") or 0)
        row["total_output_tokens"] += out_tok
        row["total_cache_creation_tokens"] += int(ev.get("cache_creation_tokens") or 0)
        t = int(ev.get("t", 0))
        if t < row["first_fire"]:
            row["first_fire"] = t
        if t > row["last_fire"]:
            row["last_fire"] = t
        # Keep the most-recent cwd seen for this session.
        if ev.get("cwd"):
            row["cwd"] = ev["cwd"]
    sessions = sorted(by_session.values(), key=lambda r: r["last_fire"], reverse=True)
    return {
        "window_minutes": window_minutes,
        "since_ts": since,
        "now_ts": int(time.time()),
        "session_count": len(sessions),
        "total_fires": sum(r["fires"] for r in sessions),
        "total_parse_ok_fires": sum(r["parse_ok_fires"] for r in sessions),
        "total_zero_token_fires": sum(r["zero_token_fires"] for r in sessions),
        "sessions": sessions,
    }


@mcp.tool()
def list_species() -> list[dict[str, Any]]:
    """List 3 randomly-sampled starter species. Re-rolls on each call."""
    return [
        {
            "id": sp.id,
            "display_name": sp.display_name,
            "kind": sp.kind,
            "blurb": sp.blurb,
            "base_stats": {
                "hp": sp.base_hp, "atk": sp.base_atk, "def": sp.base_def,
                "spd": sp.base_spd, "luck": sp.base_luck,
            },
        }
        for sp in species.random_starters(3)
    ]


@mcp.tool()
def choose_buddy(species_id: str, name: str) -> dict[str, Any]:
    """Pick a starter species and name it. Fails if a buddy already exists."""
    sp = species.get(species_id)  # raises KeyError if invalid
    name = name.strip()
    if not name or len(name) > 20:
        raise ValueError("name must be 1-20 non-whitespace chars")
    events = drain_xp_log()

    def fn(state: State) -> None:
        if state.buddy is not None:
            raise ValueError(f"already have buddy {state.buddy.name}; use reset_buddy to start over")
        stats = Stats(hp=sp.base_hp, atk=sp.base_atk, def_=sp.base_def,
                      spd=sp.base_spd, luck=sp.base_luck,
                      int_=5, res=5)
        personality = personalities.roll_for_species(sp.id, random.Random())
        traits = dict(personality.traits)
        max_mood = 80 + 2 * traits["curiosity"]
        max_stamina = 80 + 2 * traits["patience"]
        state.buddy = Buddy(
            species=sp.id, name=name, stats=stats,
            current_hp=sp.base_hp, traits=traits,
            personality=personality.id,
            mood=max_mood, max_mood=max_mood,
            stamina=max_stamina, max_stamina=max_stamina,
            current_mana=5 + stats.int_ * 2,
        )
        state.add_event(
            f"chose {name} the {personality.display_name} {sp.display_name}!"
        )
        newly = skills.check_and_grant_skills(state.buddy)
        for sid in newly:
            try:
                s = skills.get(sid)
                state.add_event(f"{name} learned {s.name}!")
            except KeyError:
                pass
        _sync_apply(state, events)

    state = mutate_state(fn)
    return _snapshot(state)


@mcp.tool()
def rename_buddy(name: str) -> dict[str, Any]:
    """Rename the current buddy."""
    name = name.strip()
    if not name or len(name) > 20:
        raise ValueError("name must be 1-20 non-whitespace chars")
    events = drain_xp_log()

    def fn(state: State) -> None:
        b = _require_buddy(state)
        old = b.name
        b.name = name
        state.add_event(f"renamed {old} → {name}")
        _sync_apply(state, events)

    return _snapshot(mutate_state(fn))


@mcp.tool()
def allocate_stats(
    hp: int = 0, atk: int = 0, def_: int = 0, spd: int = 0, luck: int = 0,
    int_: int = 0, res: int = 0,
) -> dict[str, Any]:
    """Spend unallocated stat points. All values must be non-negative; total ≤ unspent pool.

    The parameters `def_` and `int_` have trailing underscores to avoid Python's
    reserved word / builtin shadow. When calling this tool from Claude, pass the
    keys `def_` and `int_` with integer values.
    """
    allocations = {
        "hp": hp, "atk": atk, "def_": def_, "spd": spd, "luck": luck,
        "int_": int_, "res": res,
    }
    for k, v in allocations.items():
        if v < 0:
            raise ValueError(f"{k} must be ≥ 0")
    total = sum(allocations.values())
    if total == 0:
        raise ValueError("must allocate at least 1 point")

    events = drain_xp_log()

    def fn(state: State) -> None:
        b = _require_buddy(state)
        _sync_apply(state, events)  # drain first: level-ups grant more points
        if total > b.stat_points_unspent:
            raise ValueError(f"only {b.stat_points_unspent} points available, tried to spend {total}")
        b.stats.hp += allocations["hp"]
        b.stats.atk += allocations["atk"]
        b.stats.def_ += allocations["def_"]
        b.stats.spd += allocations["spd"]
        b.stats.luck += allocations["luck"]
        b.stats.int_ += allocations["int_"]
        b.stats.res += allocations["res"]
        b.stat_points_unspent -= total
        if allocations["hp"]:
            b.current_hp += allocations["hp"]  # healed by the new ceiling
        state.add_event(f"allocated {total} stat points")
        newly = skills.check_and_grant_skills(b)
        for sid in newly:
            try:
                s = skills.get(sid)
                state.add_event(f"{b.name} learned {s.name}!")
            except KeyError:
                pass

    return _snapshot(mutate_state(fn))


@mcp.tool()
def list_skills() -> dict[str, Any]:
    """List every skill the buddy knows and which are currently active.

    Returns a dict with `known` (all learned) and `active` (equipped, ≤4).
    Each entry has id, name, description, mana_cost, trigger, effect, magnitude.
    """
    state = mutate_state(lambda s: None)
    b = _require_buddy(state)

    def _entry(sid: str) -> dict[str, Any]:
        try:
            sk = skills.get(sid)
        except KeyError:
            return {"id": sid, "name": sid, "description": "(unknown skill)"}
        return {
            "id": sk.id, "name": sk.name, "description": sk.description,
            "mana_cost": sk.mana_cost, "trigger": sk.trigger,
            "effect": sk.effect, "magnitude": sk.magnitude,
        }

    return {
        "known": [_entry(sid) for sid in b.known_skills],
        "active": [_entry(sid) for sid in b.active_skills],
        "slot_cap": skills.ACTIVE_SLOT_CAP,
    }


@mcp.tool()
def set_active_skills(skill_ids: list[str]) -> dict[str, Any]:
    """Replace the buddy's active-skill loadout.

    `skill_ids` must be a subset of known_skills with no duplicates and at most 4 entries.
    """
    if len(skill_ids) > skills.ACTIVE_SLOT_CAP:
        raise ValueError(f"max {skills.ACTIVE_SLOT_CAP} active skills (got {len(skill_ids)})")
    if len(set(skill_ids)) != len(skill_ids):
        raise ValueError("duplicate skill ids")
    events = drain_xp_log()

    def fn(state: State) -> None:
        b = _require_buddy(state)
        _sync_apply(state, events)
        for sid in skill_ids:
            if sid not in b.known_skills:
                raise ValueError(f"{sid!r} is not a known skill")
        b.active_skills = list(skill_ids)
        state.add_event(f"set active skills: {', '.join(skill_ids) or '(none)'}")

    return _snapshot(mutate_state(fn))


_MYTHIC_STAT_KEYS = {"hp", "atk", "def_", "spd", "luck", "int_", "res"}
_MYTHIC_TOTAL_CAP = 40
_MYTHIC_PER_STAT_CAP = 15


@mcp.tool()
def commit_legendary_evolution(
    display_name: str,
    blurb: str,
    stat_bonus: dict[str, int],
) -> dict[str, Any]:
    """Commit a player-unique mythic (post-apex) evolution.

    Called by Claude after the player confirms the evolution. The caller
    invents the fantastical `display_name`, `blurb`, and `stat_bonus`
    distribution; the server validates and persists them as an overlay
    on the current buddy. The underlying species id doesn't change — only
    the displayed name/blurb and stats.

    Validation:
        - display_name: 1-32 chars after stripping
        - blurb: 1-200 chars after stripping
        - stat_bonus keys: subset of {hp, atk, def_, spd, luck, int_, res}
        - stat_bonus values: non-negative ints
        - sum(stat_bonus.values()) <= 40
        - max(stat_bonus.values()) <= 15
        - buddy must not already have a mythic overlay
        - current species must have mythic_at set and buddy.level >= mythic_at
    """
    # Input sanitation
    dn = (display_name or "").strip()
    bl = (blurb or "").strip()
    if not (1 <= len(dn) <= 32):
        raise ValueError("display_name must be 1-32 chars")
    if not (1 <= len(bl) <= 200):
        raise ValueError("blurb must be 1-200 chars")
    if not isinstance(stat_bonus, dict):
        raise ValueError("stat_bonus must be a dict of stat name → int")
    clean: dict[str, int] = {}
    for k, v in stat_bonus.items():
        if k not in _MYTHIC_STAT_KEYS:
            raise ValueError(
                f"unknown stat {k!r}; must be one of {sorted(_MYTHIC_STAT_KEYS)}"
            )
        try:
            iv = int(v)
        except (TypeError, ValueError):
            raise ValueError(f"stat_bonus[{k!r}] must be an int")
        if iv < 0:
            raise ValueError(f"stat_bonus[{k!r}] must be >= 0")
        if iv > _MYTHIC_PER_STAT_CAP:
            raise ValueError(
                f"stat_bonus[{k!r}]={iv} exceeds per-stat cap of {_MYTHIC_PER_STAT_CAP}"
            )
        if iv > 0:
            clean[k] = iv
    total = sum(clean.values())
    if total > _MYTHIC_TOTAL_CAP:
        raise ValueError(
            f"stat_bonus total {total} exceeds cap of {_MYTHIC_TOTAL_CAP}"
        )
    if total == 0:
        raise ValueError("stat_bonus must allocate at least 1 point somewhere")

    events = drain_xp_log()

    def fn(state: State) -> None:
        b = _require_buddy(state)
        _sync_apply(state, events)
        sp = species.get(b.species)
        if b.mythic is not None:
            raise ValueError(
                f"{b.name} has already ascended into {b.mythic.display_name}"
            )
        if sp.mythic_at is None:
            raise ValueError(
                f"{sp.display_name} cannot become mythic — not a qualifying apex form"
            )
        if b.level < sp.mythic_at:
            raise ValueError(
                f"{b.name} must reach Lv{sp.mythic_at} before invoking mythic evolution "
                f"(currently Lv{b.level})"
            )
        import time as _time
        overlay = MythicOverlay(
            display_name=dn,
            blurb=bl,
            committed_at=int(_time.time()),
            stat_bonus=dict(clean),
        )
        for k, v in clean.items():
            setattr(b.stats, k, getattr(b.stats, k) + v)
        b.current_hp = b.stats.hp  # capstone full heal
        b.mythic = overlay
        state.add_event(f"{b.name} ascended into {dn}!")

    return _snapshot(mutate_state(fn))


@mcp.tool()
def commit_evolution(species_id: str) -> dict[str, Any]:
    """Evolve the buddy into a chosen branch.

    The buddy must have reached the source species's evolves_at level AND
    every entry in the chosen Evolution's `requirements` dict must be met.
    On success the buddy swaps species, gains the branch's stat_bonus,
    full-heals, and resets to Lv1.
    """
    events = drain_xp_log()

    def fn(state: State) -> None:
        b = _require_buddy(state)
        _sync_apply(state, events)
        sp = species.get(b.species)
        if sp.evolves_at is None or not sp.evolutions:
            raise ValueError(f"{sp.display_name} has no further evolutions")
        if b.level < sp.evolves_at:
            raise ValueError(
                f"{b.name} must reach Lv{sp.evolves_at} before evolving "
                f"(currently Lv{b.level})"
            )
        evo = next(
            (e for e in sp.evolutions if e.evolved_species_id == species_id),
            None,
        )
        if evo is None:
            valid = ", ".join(e.evolved_species_id for e in sp.evolutions)
            raise ValueError(
                f"unknown evolution {species_id!r}; choose one of: {valid}"
            )
        info = species.branch_eligibility(evo, b.stats)
        if not info["eligible"]:
            unmet = [
                f"{c['stat']} {c['actual']}/{c['required']}"
                for c in info["checks"] if not c["met"]
            ]
            raise ValueError(
                f"{b.name} cannot evolve into {info['display_name']} yet — "
                f"needs: {', '.join(unmet)}"
            )
        new_sp = species.get(evo.evolved_species_id)
        old_name = sp.display_name
        b.species = new_sp.id
        for k, delta in evo.stat_bonus.items():
            setattr(b.stats, k, getattr(b.stats, k) + delta)
        b.current_hp = b.stats.hp
        b.current_mana = b.max_mana
        b.level = 1
        b.xp = 0
        state.add_event(f"{b.name} evolved from {old_name} into {new_sp.display_name}!")
        newly: list[str] = []
        if evo.grants_skill and skills._learn(b, evo.grants_skill):
            newly.append(evo.grants_skill)
        newly.extend(skills.check_and_grant_skills(b))
        for sid in newly:
            try:
                line = f"{b.name} learned {skills.get(sid).name}!"
            except KeyError:
                line = f"{b.name} learned {sid}!"
            state.add_event(line)

    return _snapshot(mutate_state(fn))


@mcp.tool()
def list_zones() -> list[dict[str, Any]]:
    """List the available quest zones. Each zone has a recommended level, a
    themed stat profile, and several quests inside. When you start a quest,
    the server smart-picks one from the chosen zone based on the buddy's
    stats — the player picks a zone, not a specific quest.
    """
    out: list[dict[str, Any]] = []
    for z in quests.list_zones():
        qdefs = [quests.get(qid) for qid in z.quest_ids]
        out.append({
            "id": z.id,
            "name": z.name,
            "recommended_level": z.recommended_level,
            "blurb": z.blurb,
            "quest_count": len(qdefs),
            "difficulty_range": [
                min(q.difficulty for q in qdefs),
                max(q.difficulty for q in qdefs),
            ],
            "xp_range": [
                min(q.xp_success_range[0] for q in qdefs),
                max(q.xp_success_range[1] for q in qdefs),
            ],
            "key_stats": sorted({
                k.rstrip("_") for q in qdefs for k in q.key_stats
            }),
            "duration_range_human": [
                f"{min(q.duration_s for q in qdefs) // 60}m",
                f"{max(q.duration_s for q in qdefs) // 60}m",
            ],
            "quests": [
                {
                    "id": q.id,
                    "name": q.name,
                    "key_stats": [k.rstrip("_") for k in q.key_stats],
                    "difficulty": q.difficulty,
                    "category": q.category,
                    "duration_human": f"{q.duration_s // 60}m",
                    "blurb": q.blurb,
                }
                for q in qdefs
            ],
        })
    return out


@mcp.tool()
def start_quest(zone_id: str) -> dict[str, Any]:
    """Send the buddy to a zone. The server smart-picks a quest from the zone
    based on the buddy's stats (the buddy leans toward quests it's suited for,
    but with variance). Returns the rolled quest name + estimated success
    probability in the response. Fails if a quest is already active.
    """
    valid_zone_ids = [z.id for z in quests.list_zones()]
    if zone_id not in valid_zone_ids:
        raise ValueError(
            f"unknown zone {zone_id!r}; valid zones: {', '.join(valid_zone_ids)}"
        )
    events = drain_xp_log()
    rolled: dict[str, Any] = {}

    def fn(state: State) -> None:
        b = _require_buddy(state)
        _sync_apply(state, events)
        qdef, prob = quests.start(b, zone_id=zone_id)
        rolled["rolled_quest_id"] = qdef.id
        rolled["rolled_quest_name"] = qdef.name
        rolled["estimated_success"] = round(prob, 2)
        state.add_event(
            f"{b.name} set off to {qdef.name} "
            f"(~{int(prob * 100)}% success)"
        )

    snap = _snapshot(mutate_state(fn))
    snap.update(rolled)
    snap["display"] = (
        f"{snap['buddy']['name']} set off to {rolled['rolled_quest_name']} "
        f"(~{int(rolled['estimated_success'] * 100)}% success, "
        f"{snap['buddy']['quest']['remaining_s']}s). "
        f"Run /buddy claim when done."
    )
    return snap


@mcp.tool()
def check_quest() -> dict[str, Any]:
    """Check progress of the current quest (no claim, no state change beyond XP sync)."""
    events = drain_xp_log()

    def fn(state: State) -> None:
        _sync_apply(state, events)

    return _snapshot(mutate_state(fn))


@mcp.tool()
def claim_quest() -> dict[str, Any]:
    """Claim a completed quest, rolling success/failure and applying rewards."""
    events = drain_xp_log()
    captured: dict[str, Any] = {}

    def fn(state: State) -> None:
        b = _require_buddy(state)
        _sync_apply(state, events)
        if b.quest is None:
            raise ValueError("no active quest to claim")
        if not b.quest.is_done():
            raise ValueError(f"quest not finished: {b.quest.remaining()}s left")
        result = quests.claim(b)
        fired_names: list[str] = []
        for sid in result.fired_skills:
            try:
                fired_names.append(skills.get(sid).name)
            except KeyError:
                fired_names.append(sid)

        state.add_event(quests.format_claim_event_line(result, fired_names))
        leveling.check_level_ups(state)

        captured["result"] = result
        captured["fired_names"] = fired_names

    state = mutate_state(fn)
    snap = _snapshot(state)
    result: quests.QuestResult = captured["result"]
    snap["claim_result"] = {
        "success": result.success,
        "xp": result.xp,
        "items": list(result.items),
        "hp_damage": result.hp_damage,
        "flavor": result.flavor,
        "probability": result.probability,
        "difficulty": result.difficulty,
        "stat_score": result.stat_score,
        "weakest_stat": (result.weakest_stat.rstrip("_") if result.weakest_stat else None),
        "fail_narrative": list(result.fail_narrative),
        "combat_log": list(result.combat_log),
        "defeated_by": result.defeated_by,
        "fired_skills": list(captured["fired_names"]),
        "mana_cost": result.mana_cost,
        "mana_cast": result.mana_cast,
    }
    snap["display"] = quests.format_claim_event_line(result, captured["fired_names"])
    return snap


@mcp.tool()
def cancel_quest() -> dict[str, Any]:
    """Abort the current quest. Buddy keeps all XP earned so far but gets no quest reward."""
    events = drain_xp_log()

    def fn(state: State) -> None:
        b = _require_buddy(state)
        _sync_apply(state, events)
        if b.quest is None:
            raise ValueError("no active quest")
        qid = b.quest.id
        b.quest = None
        b.combat = None
        state.add_event(f"cancelled {qid}")

    return _snapshot(mutate_state(fn))


@mcp.tool()
def reset_buddy(confirm: bool = False) -> dict[str, Any]:
    """DEV ONLY: wipe the current buddy so a new one can be chosen. Must pass confirm=True."""
    if not confirm:
        raise ValueError("pass confirm=True to actually reset")

    def fn(state: State) -> None:
        state.buddy = None
        state.recent_events = []
        state.add_event("buddy reset")

    return _snapshot(mutate_state(fn))


@mcp.tool()
def run_migration(dry_run: bool = False) -> dict[str, Any]:
    """Clean up pre-v0.4.0 buddy artifacts: legacy hook entries + statusLine
    in ~/.claude/settings.json, user-scope MCP server registrations named
    `buddy` or `mcp-creature-bot`, and shipped `/buddy*` files under
    ~/.claude/commands/. Settings.json is backed up with a timestamped
    suffix before any mutation.

    Idempotent — writes a marker in $CLAUDE_PLUGIN_DATA so subsequent calls
    report `already-migrated`. Pass `dry_run=true` to preview the report
    without making changes.

    Returns a dict with:
      status            — "migrated" | "nothing-to-do" | "already-migrated"
                          | "would-migrate" (dry-run with findings)
      legacy_hooks      — list of {event, command} entries stripped
      legacy_statusline — command removed, or null
      legacy_mcp_servers — user-scope MCP names detected
      removed_mcp_servers — names actually removed (on non-dry-run)
      legacy_commands   — ~/.claude/commands/ files detected
      deleted_commands  — command files actually deleted (on non-dry-run)
      settings_backup   — path to the settings.json backup (on non-dry-run)
    """
    import migrate
    return migrate.run_legacy_migration(dry_run=dry_run)
