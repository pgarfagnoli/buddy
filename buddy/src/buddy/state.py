"""Persistent buddy state with multi-process concurrency.

Locking rules:
- Always open a fresh fd for locking; never cache.
- Use fcntl.flock (not fcntl.lockf) so closing fds doesn't drop other processes' locks.
- Mutations: exclusive flock on state.lock, read state.json, apply, atomic tmp+rename write.
- Reads: shared flock on state.lock, or lockless (json is atomically replaced).
"""
from __future__ import annotations

import fcntl
import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from . import paths

STATE_VERSION = 1
EVENT_RING_SIZE = 20


@dataclass
class Quest:
    id: str
    started_at: int  # epoch seconds
    duration_s: int

    def elapsed(self, now: Optional[int] = None) -> int:
        return max(0, (now or int(time.time())) - self.started_at)

    def remaining(self, now: Optional[int] = None) -> int:
        return max(0, self.duration_s - self.elapsed(now))

    def is_done(self, now: Optional[int] = None) -> bool:
        return self.remaining(now) == 0


@dataclass
class Stats:
    hp: int = 10
    atk: int = 5
    def_: int = 5
    spd: int = 5
    luck: int = 5
    int_: int = 5
    res: int = 5

    def total(self) -> int:
        return (
            self.hp + self.atk + self.def_ + self.spd
            + self.luck + self.int_ + self.res
        )


@dataclass
class Combat:
    """Live encounter state stored on the buddy while a combat round is in flight."""
    enemy_id: str
    enemy_hp: int
    enemy_max_hp: int
    started_at: int
    last_round_at: int
    last_attacker: Optional[str] = None  # "buddy" | "enemy" | None — drives pose animation
    next_buddy_strike_at: int = 0        # epoch s; 0 = "uninitialized, set on first tick"
    next_enemy_strike_at: int = 0
    rampage_stacks: int = 0              # +1 per landed buddy strike, capped at 5 in _buddy_attack
    enemy_poison_dmg: int = 0            # damage applied per strike while strikes_left > 0
    enemy_poison_strikes_left: int = 0
    buddy_poison_dmg: int = 0
    buddy_poison_strikes_left: int = 0
    engaged_skills: list[str] = field(default_factory=list)  # skills that paid MP at spawn and are "on" for this encounter
    log: list[str] = field(default_factory=list)


@dataclass
class MythicOverlay:
    """Player-unique post-apex evolution. Persists on the buddy and overrides
    display_name / blurb without changing the underlying species id (so sprite
    lookup, kind, and the species registry keep working unchanged).
    """
    display_name: str
    blurb: str
    committed_at: int
    stat_bonus: dict[str, int] = field(default_factory=dict)


@dataclass
class Buddy:
    species: str
    name: str
    level: int = 1
    xp: int = 0
    stats: Stats = field(default_factory=Stats)
    current_hp: int = 10
    stat_points_unspent: int = 0
    inventory: list[str] = field(default_factory=list)
    quest: Optional[Quest] = None
    last_prompt_at: int = 0
    prompts_count: int = 0
    mythic: Optional[MythicOverlay] = None
    traits: dict[str, int] = field(default_factory=dict)
    personality: str = ""
    mood: int = 100
    max_mood: int = 100
    stamina: int = 100
    max_stamina: int = 100
    current_mana: int = 0
    known_skills: list[str] = field(default_factory=list)
    active_skills: list[str] = field(default_factory=list)
    combat: Optional[Combat] = None
    last_combat_spawn_at: int = 0
    idle_flavor: str = ""  # last idle vignette text — rendered under the sprite when idle

    @property
    def max_hp(self) -> int:
        return self.stats.hp

    @property
    def max_mana(self) -> int:
        return 5 + self.stats.int_ * 2


@dataclass
class State:
    version: int = STATE_VERSION
    buddy: Optional[Buddy] = None
    recent_events: list[str] = field(default_factory=list)  # ring buffer

    def add_event(self, line: str) -> None:
        self.recent_events.append(f"[{time.strftime('%H:%M:%S')}] {line}")
        if len(self.recent_events) > EVENT_RING_SIZE:
            self.recent_events = self.recent_events[-EVENT_RING_SIZE:]


# ─── (de)serialization ──────────────────────────────────────────────────────

# Naturalization rename pass: old fantasy species ids resolve to their
# real-species replacements on load so existing buddies don't break.
# Populated as Phase 2 species renames land. Keys = legacy id, value =
# new real-species id. Applied inside _buddy_from_dict.
_LEGACY_SPECIES_IDS: dict[str, str] = {
    # Wyrm chain → real cave-dweller line (olm/waterdog).
    "pond_wyrm": "waterdog",
    "lake_wyrm": "waterdog",
    "crystal_wyrm": "waterdog",
}


def _buddy_to_dict(b: Buddy) -> dict[str, Any]:
    d = {
        "species": b.species,
        "name": b.name,
        "level": b.level,
        "xp": b.xp,
        "stats": {"hp": b.stats.hp, "atk": b.stats.atk, "def": b.stats.def_,
                  "spd": b.stats.spd, "luck": b.stats.luck,
                  "int": b.stats.int_, "res": b.stats.res},
        "current_hp": b.current_hp,
        "stat_points_unspent": b.stat_points_unspent,
        "inventory": list(b.inventory),
        "quest": (
            {"id": b.quest.id, "started_at": b.quest.started_at, "duration_s": b.quest.duration_s}
            if b.quest else None
        ),
        "last_prompt_at": b.last_prompt_at,
        "prompts_count": b.prompts_count,
        "mythic": (
            {
                "display_name": b.mythic.display_name,
                "blurb": b.mythic.blurb,
                "committed_at": b.mythic.committed_at,
                "stat_bonus": dict(b.mythic.stat_bonus),
            }
            if b.mythic else None
        ),
        "traits": dict(b.traits),
        "personality": b.personality,
        "mood": b.mood,
        "max_mood": b.max_mood,
        "stamina": b.stamina,
        "max_stamina": b.max_stamina,
        "current_mana": b.current_mana,
        "known_skills": list(b.known_skills),
        "active_skills": list(b.active_skills),
        "combat": (
            {
                "enemy_id": b.combat.enemy_id,
                "enemy_hp": b.combat.enemy_hp,
                "enemy_max_hp": b.combat.enemy_max_hp,
                "started_at": b.combat.started_at,
                "last_round_at": b.combat.last_round_at,
                "last_attacker": b.combat.last_attacker,
                "next_buddy_strike_at": b.combat.next_buddy_strike_at,
                "next_enemy_strike_at": b.combat.next_enemy_strike_at,
                "rampage_stacks": b.combat.rampage_stacks,
                "enemy_poison_dmg": b.combat.enemy_poison_dmg,
                "enemy_poison_strikes_left": b.combat.enemy_poison_strikes_left,
                "buddy_poison_dmg": b.combat.buddy_poison_dmg,
                "buddy_poison_strikes_left": b.combat.buddy_poison_strikes_left,
                "engaged_skills": list(b.combat.engaged_skills),
                "log": list(b.combat.log),
            }
            if b.combat else None
        ),
        "last_combat_spawn_at": b.last_combat_spawn_at,
        "idle_flavor": b.idle_flavor,
    }
    return d


def _buddy_from_dict(d: dict[str, Any]) -> Buddy:
    s = d.get("stats", {})
    stats = Stats(
        hp=s.get("hp", 10), atk=s.get("atk", 5), def_=s.get("def", 5),
        spd=s.get("spd", 5), luck=s.get("luck", 5),
        int_=s.get("int", 5), res=s.get("res", 5),
    )
    q = d.get("quest")
    quest = Quest(id=q["id"], started_at=q["started_at"], duration_s=q["duration_s"]) if q else None
    c = d.get("combat")
    combat = (
        Combat(
            enemy_id=str(c["enemy_id"]),
            enemy_hp=int(c["enemy_hp"]),
            enemy_max_hp=int(c["enemy_max_hp"]),
            started_at=int(c["started_at"]),
            last_round_at=int(c["last_round_at"]),
            last_attacker=(str(c["last_attacker"]) if c.get("last_attacker") else None),
            next_buddy_strike_at=int(c.get("next_buddy_strike_at", 0)),
            next_enemy_strike_at=int(c.get("next_enemy_strike_at", 0)),
            rampage_stacks=int(c.get("rampage_stacks", 0)),
            enemy_poison_dmg=int(c.get("enemy_poison_dmg", 0)),
            enemy_poison_strikes_left=int(c.get("enemy_poison_strikes_left", 0)),
            buddy_poison_dmg=int(c.get("buddy_poison_dmg", 0)),
            buddy_poison_strikes_left=int(c.get("buddy_poison_strikes_left", 0)),
            engaged_skills=[str(x) for x in c.get("engaged_skills", [])],
            log=[str(x) for x in c.get("log", [])],
        )
        if c else None
    )
    m = d.get("mythic")
    mythic = (
        MythicOverlay(
            display_name=m["display_name"],
            blurb=m["blurb"],
            committed_at=int(m.get("committed_at", 0)),
            stat_bonus=dict(m.get("stat_bonus") or {}),
        )
        if m else None
    )
    traits_raw = d.get("traits") or {}
    traits = {
        k: int(v) for k, v in traits_raw.items()
        if isinstance(v, (int, float))
    }
    personality = str(d.get("personality", "") or "")
    if not personality:
        # Legacy save: derive a label from whatever traits are there,
        # or seed both when nothing at all is stored.
        from . import personalities  # local import avoids cycles at module load
        if traits:
            personality = personalities.closest_to_traits(traits).id
        else:
            personality = "balanced"
            traits = dict(personalities.PERSONALITIES["balanced"].traits)
    species_id = _LEGACY_SPECIES_IDS.get(d["species"], d["species"])
    return Buddy(
        species=species_id, name=d["name"], level=d.get("level", 1), xp=d.get("xp", 0),
        stats=stats, current_hp=d.get("current_hp", stats.hp),
        stat_points_unspent=d.get("stat_points_unspent", 0),
        inventory=list(d.get("inventory", [])), quest=quest,
        last_prompt_at=d.get("last_prompt_at", 0),
        prompts_count=d.get("prompts_count", 0),
        mythic=mythic,
        traits=traits,
        personality=personality,
        mood=int(d.get("mood", 100)),
        max_mood=int(d.get("max_mood", 100)),
        stamina=int(d.get("stamina", 100)),
        max_stamina=int(d.get("max_stamina", 100)),
        current_mana=int(d.get("current_mana", 0)),
        known_skills=[str(x) for x in d.get("known_skills", [])],
        active_skills=[str(x) for x in d.get("active_skills", [])],
        combat=combat,
        last_combat_spawn_at=int(d.get("last_combat_spawn_at", 0)),
        idle_flavor=str(d.get("idle_flavor", "") or ""),
    )


def state_to_dict(s: State) -> dict[str, Any]:
    return {
        "version": s.version,
        "buddy": _buddy_to_dict(s.buddy) if s.buddy else None,
        "recent_events": list(s.recent_events),
    }


def state_from_dict(d: dict[str, Any]) -> State:
    return State(
        version=d.get("version", STATE_VERSION),
        buddy=_buddy_from_dict(d["buddy"]) if d.get("buddy") else None,
        recent_events=list(d.get("recent_events", [])),
    )


# ─── locking primitives ─────────────────────────────────────────────────────

@contextmanager
def _flock(path: Path, exclusive: bool) -> Iterator[None]:
    # Ensure the lock file exists; open a fresh fd each call.
    path.touch(exist_ok=True)
    fd = os.open(path, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


# ─── public API ─────────────────────────────────────────────────────────────

def load_state() -> State:
    """Read current state. Returns empty State if file missing/corrupt."""
    p = paths.state_file()
    if not p.exists():
        return State()
    try:
        with _flock(paths.state_lock(), exclusive=False):
            data = json.loads(p.read_text())
        return state_from_dict(data)
    except (json.JSONDecodeError, KeyError, OSError):
        return State()


def save_state(state: State) -> None:
    """Atomically write state. Caller must already hold the lock if coordinating."""
    p = paths.state_file()
    tmp = p.with_suffix(".json.tmp")
    try:
        data = json.dumps(state_to_dict(state), indent=2)
    except (TypeError, ValueError) as exc:
        import sys
        print(f"[buddy] save_state serialization failed: {exc}", file=sys.stderr)
        raise
    tmp.write_text(data)
    os.rename(tmp, p)


def mutate_state(fn: Callable[[State], None]) -> State:
    """Exclusive read-modify-write. fn mutates state in place."""
    with _flock(paths.state_lock(), exclusive=True):
        p = paths.state_file()
        if p.exists():
            try:
                state = state_from_dict(json.loads(p.read_text()))
            except (json.JSONDecodeError, KeyError):
                state = State()
        else:
            state = State()
        fn(state)
        save_state(state)
        return state


def init_state_if_missing() -> None:
    if not paths.state_file().exists():
        mutate_state(lambda s: None)


# ─── xp event log ───────────────────────────────────────────────────────────

def append_xp_event(event: dict[str, Any]) -> None:
    """Append one XP event, serialized with drain_xp_log via xp.log.lock.

    Holds an exclusive flock on xp.log.lock so a concurrent drain can't
    rename-and-unlink the file out from under our write.
    """
    line = json.dumps(event, separators=(",", ":")) + "\n"
    with _flock(paths.xp_log_lock(), exclusive=True):
        fd = os.open(paths.xp_log(), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)


def drain_xp_log() -> list[dict[str, Any]]:
    """Atomically claim all pending XP events.

    Holds an exclusive flock on xp.log.lock, reads xp.log in place, then
    truncates it to zero. Appenders contending on the same lock see a
    consistent before/after view — no rename dance, no lost writes.
    """
    src = paths.xp_log()
    events: list[dict[str, Any]] = []
    with _flock(paths.xp_log_lock(), exclusive=True):
        if not src.exists():
            return []
        try:
            raw = src.read_text()
        except FileNotFoundError:
            return []
        fd = os.open(src, os.O_WRONLY)
        try:
            os.ftruncate(fd, 0)
        finally:
            os.close(fd)
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


# ─── hook breadcrumb log ────────────────────────────────────────────────────

HOOKS_LOG_MAX_LINES = 500


def append_hook_event(event: dict[str, Any]) -> None:
    """Append one diagnostic breadcrumb to hooks.log. Never drained.

    Rotates by trimming to the last HOOKS_LOG_MAX_LINES lines when the file
    grows past 2x that cap. Serialized under xp.log.lock so it shares fate
    with the XP append — if the XP append made it, the breadcrumb did too.
    """
    line = json.dumps(event, separators=(",", ":")) + "\n"
    p = paths.hooks_log()
    with _flock(paths.xp_log_lock(), exclusive=True):
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
        try:
            stat = p.stat()
        except FileNotFoundError:
            return
        # Cheap rotation check: only read+rewrite when byte size crosses the cap.
        if stat.st_size > HOOKS_LOG_MAX_LINES * 512:
            try:
                lines = p.read_text().splitlines()
            except OSError:
                return
            if len(lines) > HOOKS_LOG_MAX_LINES:
                tail = lines[-HOOKS_LOG_MAX_LINES:]
                tmp = p.with_suffix(".log.tmp")
                tmp.write_text("\n".join(tail) + "\n")
                os.rename(tmp, p)


def read_hook_events(since_ts: int = 0) -> list[dict[str, Any]]:
    """Return hook breadcrumbs with t >= since_ts, oldest first."""
    p = paths.hooks_log()
    if not p.exists():
        return []
    with _flock(paths.xp_log_lock(), exclusive=True):
        try:
            raw = p.read_text()
        except OSError:
            return []
    out: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if int(ev.get("t", 0)) >= since_ts:
            out.append(ev)
    return out
