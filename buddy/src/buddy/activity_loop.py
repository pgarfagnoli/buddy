"""Background activity loop: cron-like tick that decides autonomous buddy actions.

Spawned as a detached subprocess by `server.start_pane`. Runs forever, sleeping
between ticks; on each tick it consults `_decide()` (Claude Haiku via
`claude -p --bare`, with a deterministic dice-roll fallback) and applies the
resulting `IdleDecision` via the shared state API.

Design notes
------------
- Singleton enforced by a non-blocking flock on `paths.activity_loop_lock()`:
  a second instance exits 0 silently.
- `--bare` strips hooks/MCP/skills/statusline/auto-memory from the subprocess
  `claude`, so the decision call CANNOT recursively fire this project's own
  Stop hook.
- All state mutations go through `state.mutate_state`, same as every other
  code path.
"""
from __future__ import annotations

import fcntl
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import time
import traceback
from types import FrameType
from typing import Any, Optional

from . import paths, quests, vignettes
from .quests import IdleDecision
from .state import Buddy, State, load_state, mutate_state

# ─── tunables ───────────────────────────────────────────────────────────────

TICK_INTERVAL_S = int(os.environ.get("BUDDY_TICK_S", "600"))  # 10 min
TICK_JITTER = 0.25                                             # ±25%
IDLE_THRESHOLD_S = int(os.environ.get("BUDDY_IDLE_THRESHOLD_S", "120"))
SUBPROCESS_TIMEOUT_S = 45
MODEL_ID = "claude-haiku-4-5-20251001"
LOG_MAX_LINES = 500

# ─── module state ───────────────────────────────────────────────────────────

_stop = False
_lock_fd: Optional[int] = None


def _shutdown(signum: int, frame: Optional[FrameType]) -> None:  # noqa: ARG001
    global _stop
    _stop = True


# ─── singleton ──────────────────────────────────────────────────────────────

def _acquire_singleton() -> bool:
    """Non-blocking exclusive flock. Returns True on acquire, False if another
    instance already holds it (caller should exit 0).
    """
    global _lock_fd
    lock_path = paths.activity_loop_lock()
    lock_path.touch(exist_ok=True)
    _lock_fd = os.open(lock_path, os.O_RDWR)
    try:
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(_lock_fd)
        _lock_fd = None
        return False
    return True


def _release_singleton() -> None:
    global _lock_fd
    if _lock_fd is not None:
        try:
            fcntl.flock(_lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(_lock_fd)
            _lock_fd = None


def _write_pid() -> None:
    paths.activity_loop_pid().write_text(str(os.getpid()))


def _clear_pid() -> None:
    try:
        paths.activity_loop_pid().unlink()
    except FileNotFoundError:
        pass


# ─── tick log ───────────────────────────────────────────────────────────────

def _log_tick(record: dict[str, Any]) -> None:
    record.setdefault("t", int(time.time()))
    line = json.dumps(record, separators=(",", ":")) + "\n"
    p = paths.activity_loop_log()
    try:
        with open(p, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        return
    # Cheap tail-trim when the file gets long.
    try:
        if p.stat().st_size > LOG_MAX_LINES * 256:
            lines = p.read_text().splitlines()
            if len(lines) > LOG_MAX_LINES:
                tmp = p.with_suffix(".log.tmp")
                tmp.write_text("\n".join(lines[-LOG_MAX_LINES:]) + "\n")
                os.rename(tmp, p)
    except OSError:
        pass


def _log_exc(exc: BaseException) -> None:
    _log_tick({
        "action": "error",
        "err": type(exc).__name__,
        "msg": str(exc)[:200],
    })


# ─── decision layer ─────────────────────────────────────────────────────────

_DECISION_SCHEMA = {
    "type": "object",
    "required": ["action", "reason"],
    "properties": {
        "action":   {"enum": ["noop", "idle_flavor", "start_quest"]},
        "quest_id": {"type": "string"},
        "flavor":   {"type": "string", "maxLength": 120},
        "reason":   {"type": "string", "maxLength": 160},
    },
}


def _build_prompt(state: State) -> str:
    b = state.buddy
    assert b is not None
    # Eligible real-quest pool — same gate as pick_for_idle.
    eligible = [
        q for q in quests.QUESTS.values()
        if q.difficulty <= b.level + 2 and q.category in ("combat", "gathering", "rest")
    ]
    # Keep the prompt compact — list ids + short blurbs.
    pool_lines = [
        f"  - {q.id}  ({q.category}, {q.duration_s}s, diff {q.difficulty}): {q.blurb}"
        for q in eligible
    ]
    sample_vignettes = ", ".join(v.id for v in vignettes.VIGNETTES[:6])
    recent = "\n".join(f"  - {e}" for e in state.recent_events[-5:]) or "  (none)"
    traits = b.traits or {}
    mood_pct = int(round(100 * b.mood / max(1, b.max_mood)))
    stamina_pct = int(round(100 * b.stamina / max(1, b.max_stamina)))
    return (
        f"You are deciding what an RPG pet does while its owner is away from the keyboard.\n\n"
        f"Buddy: {b.name} the {b.species} (Lv{b.level}, HP {b.current_hp}/{b.stats.hp}, MP {b.current_mana}/{b.max_mana}).\n"
        f"Mood: {b.mood}/{b.max_mood} ({mood_pct}%). "
        f"Stamina: {b.stamina}/{b.max_stamina} ({stamina_pct}%).\n"
        f"Traits (0-10 scale): "
        f"curiosity {traits.get('curiosity', 5)}, "
        f"boldness {traits.get('boldness', 5)}, "
        f"patience {traits.get('patience', 5)}.\n"
        f"A tired buddy (low stamina) should rest or noop. A grumpy buddy "
        f"(low mood) prefers fun vignettes over quests.\n"
        f"Recent events:\n{recent}\n\n"
        f"Eligible tasks:\n" + ("\n".join(pool_lines) or "  (none)") + "\n\n"
        f"Choose one JSON action:\n"
        f"- 'noop' if nothing happens this tick (most common).\n"
        f"- 'idle_flavor' with a short in-character 'flavor' sentence about "
        f"something tiny the buddy does right now (e.g. like: {sample_vignettes}). "
        f"Reference the buddy by name. 120 chars max.\n"
        f"- 'start_quest' with a 'quest_id' chosen from the eligible list above. "
        f"Prefer safe gathering unless the buddy is bold.\n"
        f"Always include a short 'reason'.\n"
    )


def _call_claude_p(prompt: str) -> Optional[dict]:
    """Invoke `claude -p --bare` and parse the JSON payload. Returns None on
    any failure (missing binary, timeout, non-zero exit, unparseable output).
    """
    claude_bin = shutil.which("claude")
    if not claude_bin:
        return None
    cmd = [
        claude_bin, "-p", prompt,
        "--bare",
        "--output-format", "json",
        "--model", MODEL_ID,
        "--tools", "",
        "--json-schema", json.dumps(_DECISION_SCHEMA),
    ]
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if res.returncode != 0:
        return None
    try:
        envelope = json.loads(res.stdout)
    except json.JSONDecodeError:
        return None
    result_raw = envelope.get("result")
    if not isinstance(result_raw, str):
        return None
    try:
        return json.loads(result_raw)
    except json.JSONDecodeError:
        return None


def _validate_llm_decision(parsed: dict, state: State) -> Optional[IdleDecision]:
    """Turn a raw LLM JSON dict into a validated IdleDecision or None."""
    action = parsed.get("action")
    reason = str(parsed.get("reason", ""))[:160]
    b = state.buddy
    assert b is not None

    if action == "noop":
        return IdleDecision(action="noop", reason=reason or "llm: quiet")

    if action == "idle_flavor":
        flavor = parsed.get("flavor")
        if not isinstance(flavor, str) or not flavor.strip():
            return None
        return IdleDecision(
            action="idle_flavor",
            flavor=flavor.strip()[:120],
            reason=reason or "llm: idle_flavor",
        )

    if action == "start_quest":
        qid = parsed.get("quest_id")
        if not isinstance(qid, str) or qid not in quests.QUESTS:
            return None
        qdef = quests.QUESTS[qid]
        if qdef.difficulty > b.level + 2:
            return None
        return IdleDecision(
            action="start_quest",
            quest_id=qid,
            reason=reason or f"llm: {qid}",
        )

    return None


def _decide(state: State) -> IdleDecision:
    """Primary: `claude -p --bare`. Fallback: pick_for_idle dice."""
    assert state.buddy is not None
    try:
        parsed = _call_claude_p(_build_prompt(state))
    except Exception as exc:  # never let decision errors kill the loop
        _log_exc(exc)
        parsed = None
    if parsed is not None:
        validated = _validate_llm_decision(parsed, state)
        if validated is not None:
            return validated
    return quests.pick_for_idle(state.buddy, random.Random())


# ─── apply ──────────────────────────────────────────────────────────────────

def _apply(decision: IdleDecision) -> None:
    if decision.action == "noop":
        _log_tick({"action": "noop", "reason": decision.reason})
        return

    if decision.action == "idle_flavor":
        text = decision.flavor or ""
        if not text:
            _log_tick({"action": "noop", "reason": "empty flavor"})
            return

        def fn_flavor(s: State) -> None:
            s.add_event(text)
            if s.buddy is not None:
                bump = 2 + int(s.buddy.traits.get("curiosity", 5)) // 3
                s.buddy.mood = min(s.buddy.max_mood, s.buddy.mood + bump)

        mutate_state(fn_flavor)
        _log_tick({
            "action": "idle_flavor",
            "flavor": text,
            "reason": decision.reason,
        })
        return

    if decision.action == "start_quest":
        qid = decision.quest_id
        if not qid:
            _log_tick({"action": "noop", "reason": "missing quest_id"})
            return

        def fn_start(s: State) -> None:
            if s.buddy is None or s.buddy.quest is not None:
                return
            qdef = quests.start_specific(s.buddy, qid)
            s.add_event(f"{s.buddy.name} wandered off to {qdef.name} on its own")

        mutate_state(fn_start)
        _log_tick({
            "action": "start_quest",
            "quest": qid,
            "reason": decision.reason,
        })
        return

    _log_tick({"action": "noop", "reason": f"unknown action {decision.action!r}"})


# ─── per-tick gating ────────────────────────────────────────────────────────

def _regen() -> None:
    """Wall-clock regen step run at the top of each tick.

    Stamina ticks up by 2 + patience//2 per loop iteration (default
    ~10 min). Mood drifts up slowly when the buddy is below half its
    max — real mood recovery comes from vignettes / rest / gathering.
    """
    def fn(s: State) -> None:
        b = s.buddy
        if b is None:
            return
        p = int(b.traits.get("patience", 5))
        stamina_gain = 2 + p // 2
        b.stamina = min(b.max_stamina, b.stamina + stamina_gain)
        if b.mood < b.max_mood // 2:
            b.mood = min(b.max_mood, b.mood + 1)
    try:
        mutate_state(fn)
    except Exception as exc:
        _log_exc(exc)


def _maybe_tick() -> None:
    _regen()
    state = load_state()
    b = state.buddy
    if b is None:
        return  # no buddy yet
    if b.quest is not None:
        return  # busy — let the existing quest finish
    now = int(time.time())
    if b.last_prompt_at and now - b.last_prompt_at < IDLE_THRESHOLD_S:
        return  # user is still active; don't interrupt
    decision = _decide(state)
    _apply(decision)


# ─── main ───────────────────────────────────────────────────────────────────

def main() -> int:
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    if not _acquire_singleton():
        return 0

    _write_pid()
    _log_tick({"action": "start", "pid": os.getpid(), "interval": TICK_INTERVAL_S})
    try:
        while not _stop:
            jitter = random.uniform(1 - TICK_JITTER, 1 + TICK_JITTER)
            sleep_s = max(1.0, TICK_INTERVAL_S * jitter)
            # Sleep in short slices so SIGTERM is responsive.
            slept = 0.0
            while slept < sleep_s and not _stop:
                time.sleep(min(1.0, sleep_s - slept))
                slept += 1.0
            if _stop:
                break
            try:
                _maybe_tick()
            except Exception as exc:
                _log_exc(exc)
                traceback.print_exc(file=sys.stderr)
    finally:
        _log_tick({"action": "stop", "pid": os.getpid()})
        _clear_pid()
        _release_singleton()
    return 0


if __name__ == "__main__":
    sys.exit(main())
