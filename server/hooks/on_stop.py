"""Stop hook: on end-of-turn, read transcript, record token usage.

XP accrues at Stop rather than prompt-submit in the plugin rewrite — 1 prompt
produces 1 Stop event, so a dedicated `on_prompt` hook is no longer needed.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Claude Code invokes this script with an absolute path; bootstrap the parent
# dir onto sys.path so `import state` resolves to server/state.py.
_SERVER_DIR = Path(__file__).resolve().parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

import state  # noqa: E402


def _is_tool_result_envelope(msg: dict) -> bool:
    """True iff this `type: user` line is a tool_result wrapper, not a real prompt."""
    content = msg.get("content")
    if not isinstance(content, list) or not content:
        return False
    return all(
        isinstance(item, dict) and item.get("type") == "tool_result"
        for item in content
    )


def _sum_turn_usage(transcript_path: str) -> tuple[int, int, int]:
    """Walk the transcript JSONL backwards, summing usage from this turn's
    assistant messages. Returns (input, output, cache_creation).

    A "turn" runs from the most recent real user prompt to the end of the
    file. Tool-result envelopes are part of the current turn and are skipped
    rather than treated as boundaries. Assistant usage is deduped by
    `message.id` so multi-block responses (thinking + text + tool_use) —
    which share one usage block across several transcript lines — are
    counted once.
    """
    try:
        with open(transcript_path) as f:
            lines = f.readlines()
    except OSError:
        return (0, 0, 0)
    seen: set[str] = set()
    ti = to = tc = 0
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = d.get("type")
        if t == "user":
            msg = d.get("message") or {}
            if _is_tool_result_envelope(msg):
                continue
            break
        if t != "assistant":
            continue
        msg = d.get("message") or {}
        mid = msg.get("id")
        if isinstance(mid, str):
            if mid in seen:
                continue
            seen.add(mid)
        usage = msg.get("usage") or {}
        ti += int(usage.get("input_tokens") or 0)
        to += int(usage.get("output_tokens") or 0)
        tc += int(usage.get("cache_creation_input_tokens") or 0)
    return (ti, to, tc)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    if payload.get("stop_hook_active"):
        return 0
    transcript = payload.get("transcript_path") or ""
    session = payload.get("session_id") or ""
    if not transcript:
        return 0
    ti, to, tc = _sum_turn_usage(transcript)
    now = int(time.time())
    parse_ok = to > 0

    # Breadcrumb fires even when we parsed zero tokens, so hook_diagnostics
    # can surface "hook wired but parser broken" instead of silent failure.
    try:
        cwd = payload.get("cwd") or os.getcwd()
        state.append_hook_event({
            "t": now,
            "session": session,
            "cwd": cwd,
            "input_tokens": ti,
            "output_tokens": to,
            "cache_creation_tokens": tc,
            "parse_ok": parse_ok,
        })
    except Exception:
        pass

    if not parse_ok:
        return 0

    try:
        state.append_xp_event({
            "t": now,
            "session": session,
            "input_tokens": ti,
            "output_tokens": to,
            "cache_creation_tokens": tc,
        })
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
