"""Standalone buddy-pane renderer with animated sprites.

Reads buddy state from whichever plugin-data dir is active and repaints a
side-by-side view (sprite + stats) on a ~2s interval.  Designed to run in any
terminal — Terminal.app, iTerm, tmux pane, wezterm, kitty, etc.  Ctrl-C to
quit.

State-dir resolution (first match wins):
  1. $BUDDY_ROOT override (useful for tests).
  2. $CLAUDE_PLUGIN_DATA if the user exports it.
  3. Scan ~/.claude/plugins/data/* for a child dir containing state.json.
     Prefer a path whose basename contains "buddy" if multiple match.
  4. Legacy ~/.claude/buddy/state.json.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import sys
import time
from pathlib import Path
from typing import Optional


REFRESH_SECONDS = 2.0
CLEAR_SCREEN = "\x1b[2J\x1b[H"
HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
BAR_WIDTH = 16

# ─── ANSI helpers ─────────────────────────────────────────────────────────

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
BLUE = "\x1b[34m"
MAGENTA = "\x1b[35m"
CYAN = "\x1b[36m"
WHITE = "\x1b[37m"
BRIGHT_WHITE = "\x1b[97m"


def _visible_len(s: str) -> int:
    """Length of string excluding ANSI escape sequences."""
    import re
    return len(re.sub(r"\x1b\[[0-9;]*m", "", s))


# ─── state resolution ────────────────────────────────────────────────────

def resolve_state_file() -> Optional[Path]:
    env_root = os.environ.get("BUDDY_ROOT")
    if env_root:
        return Path(env_root).expanduser() / "state.json"
    plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if plugin_data:
        candidate = Path(plugin_data).expanduser() / "state.json"
        if candidate.exists():
            return candidate

    plugins_root = Path.home() / ".claude" / "plugins" / "data"
    if plugins_root.is_dir():
        matches = sorted(
            (p for p in plugins_root.iterdir() if (p / "state.json").exists()),
            key=lambda p: ("buddy" not in p.name.lower(), p.stat().st_mtime * -1),
        )
        if matches:
            return matches[0] / "state.json"

    legacy = Path.home() / ".claude" / "buddy" / "state.json"
    if legacy.exists():
        return legacy
    return None


def _load_state(path: Path) -> Optional[dict]:
    try:
        raw = path.read_text()
    except OSError:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


# ─── sprite loading ───────────────────────────────────────────────────────

def _resolve_sprites_dir() -> Optional[Path]:
    """Find the sprites directory — via $CLAUDE_PLUGIN_ROOT or relative to this file."""
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        d = Path(env).expanduser() / "data" / "sprites"
        if d.is_dir():
            return d
    d = Path(__file__).resolve().parent.parent / "data" / "sprites"
    if d.is_dir():
        return d
    return None


def _parse_sprite(text: str) -> tuple[list[list[str]], list[list[str]]]:
    """Parse a sprite file into (idle_frames, quest_frames)."""
    idle: list[list[str]] = []
    quest: list[list[str]] = []
    current = idle
    buf: list[str] = []
    for raw in text.splitlines():
        marker = raw.strip()
        if marker == "--FRAME--":
            if buf:
                current.append(buf)
                buf = []
            continue
        if marker == "--QUEST--":
            if buf:
                current.append(buf)
                buf = []
            current = quest
            continue
        if marker in ("--ATTACK--", "--HURT--"):
            if buf:
                current.append(buf)
                buf = []
            current = []  # discard attack/hurt for pane display
            continue
        buf.append(raw)
    if buf:
        current.append(buf)

    def _trim(frame: list[str]) -> list[str]:
        while frame and not frame[0].strip():
            frame.pop(0)
        while frame and not frame[-1].strip():
            frame.pop()
        return frame

    idle = [f for f in (_trim(f) for f in idle) if f]
    quest = [f for f in (_trim(f) for f in quest) if f]
    return idle, quest


_sprite_cache: dict[str, tuple[list[list[str]], list[list[str]]]] = {}


def _load_sprite(species_id: str, sprites_dir: Optional[Path]) -> tuple[list[list[str]], list[list[str]]]:
    """Load and cache sprite frames. Returns (idle_frames, quest_frames)."""
    if species_id in _sprite_cache:
        return _sprite_cache[species_id]
    if not sprites_dir:
        return [], []
    path = sprites_dir / f"{species_id}.txt"
    if not path.exists():
        # Try species.py fallback if available
        try:
            import species as sp_mod
            sp = sp_mod.SPECIES.get(species_id)
            if sp and sp.sprite_fallback:
                result = _load_sprite(sp.sprite_fallback, sprites_dir)
                _sprite_cache[species_id] = result
                return result
        except ImportError:
            pass
        return [], []
    try:
        result = _parse_sprite(path.read_text())
    except OSError:
        result = ([], [])
    _sprite_cache[species_id] = result
    return result


# ─── bars ─────────────────────────────────────────────────────────────────

def _bar(filled: int, total: int, color: str, width: int = BAR_WIDTH) -> str:
    if total <= 0:
        return DIM + "░" * width + RESET
    ratio = max(0.0, min(1.0, filled / total))
    lit = int(round(ratio * width))
    return color + "█" * lit + DIM + "░" * (width - lit) + RESET


def _hp_color(hp: int, max_hp: int) -> str:
    if max_hp <= 0:
        return DIM
    ratio = hp / max_hp
    if ratio > 0.5:
        return GREEN
    if ratio > 0.25:
        return YELLOW
    return RED


# ─── render ───────────────────────────────────────────────────────────────

def _render(
    state: Optional[dict],
    state_path: Optional[Path],
    width: int,
    frame_idx: int,
    sprites_dir: Optional[Path],
) -> str:
    box_w = min(width, 64)
    top = f"╭{'─' * (box_w - 2)}╮"
    bot = f"╰{'─' * (box_w - 2)}╯"
    mid = f"├{'─' * (box_w - 2)}┤"

    def _row(content: str) -> str:
        vis = _visible_len(content)
        pad = max(0, box_w - 4 - vis)
        return f"│ {content}{' ' * pad} │"

    lines: list[str] = []
    lines.append(DIM + top + RESET)
    lines.append(DIM + _row(f"{BOLD}{BRIGHT_WHITE}buddy-pane{RESET}") + RESET)
    lines.append(DIM + mid + RESET)

    if state is None:
        lines.append(DIM + _row("") + RESET)
        lines.append(DIM + _row(f"{YELLOW}(no state file found){RESET}") + RESET)
        lines.append(DIM + _row("") + RESET)
        lines.append(DIM + _row("Run /buddy:start in Claude Code.") + RESET)
        lines.append(DIM + _row("") + RESET)
        lines.append(DIM + bot + RESET)
        return "\n".join(lines)

    buddy = state.get("buddy")
    if not buddy:
        lines.append(DIM + _row("") + RESET)
        lines.append(DIM + _row(f"{YELLOW}No buddy yet.{RESET} Run /buddy:start.") + RESET)
        lines.append(DIM + _row("") + RESET)
        lines.append(DIM + bot + RESET)
        return "\n".join(lines)

    # ── sprite selection ──
    species_id = buddy.get("species", "")
    quest = buddy.get("quest")
    on_quest = quest and not quest.get("done", False)
    idle_frames, quest_frames = _load_sprite(species_id, sprites_dir)
    if on_quest and quest_frames:
        frames = quest_frames
    else:
        frames = idle_frames
    sprite_lines: list[str] = []
    if frames:
        frame = frames[frame_idx % len(frames)]
        sprite_lines = list(frame)

    # ── buddy info ──
    name = buddy.get("name", "?")
    species_info = buddy.get("species_info") or {}
    species_name = species_info.get("display_name") or species_id.replace("_", " ").title()
    level = buddy.get("level", 1)
    hp = buddy.get("current_hp", 0)
    max_hp = buddy.get("max_hp", max(1, hp))
    mp = buddy.get("current_mana", 0)
    max_mp = buddy.get("max_mana", max(1, mp))
    xp = buddy.get("xp", 0)
    xp_next = buddy.get("xp_to_next", max(1, xp))

    header = f"{BOLD}{BRIGHT_WHITE}{name}{RESET}  {DIM}({CYAN}{species_name}{RESET} {DIM}Lv{level}){RESET}"
    hp_line = f"{WHITE}HP {_bar(hp, max_hp, _hp_color(hp, max_hp))} {GREEN}{hp}{DIM}/{max_hp}{RESET}"
    mp_line = f"{WHITE}MP {_bar(mp, max_mp, BLUE)} {BLUE}{mp}{DIM}/{max_mp}{RESET}"
    xp_line = f"{WHITE}XP {_bar(xp, xp_next, YELLOW)} {YELLOW}{xp}{DIM}/{xp_next}{RESET}"

    stats = buddy.get("stats") or {}

    def _sv(k: str) -> str:
        return str(stats.get(k, stats.get(k.rstrip("_"), "?")))

    stat1 = f"{DIM}ATK {BRIGHT_WHITE}{_sv('atk')}{RESET}  {DIM}DEF {BRIGHT_WHITE}{_sv('def')}{RESET}  {DIM}SPD {BRIGHT_WHITE}{_sv('spd')}{RESET}"
    stat2 = f"{DIM}LCK {BRIGHT_WHITE}{_sv('luck')}{RESET}  {DIM}INT {BRIGHT_WHITE}{_sv('int')}{RESET}  {DIM}RES {BRIGHT_WHITE}{_sv('res')}{RESET}"

    unspent = buddy.get("stat_points_unspent", 0)
    unspent_line = f"{YELLOW}{unspent} unspent pts{RESET}  {DIM}/buddy:allocate{RESET}" if unspent else ""

    if quest:
        q_name = quest.get("name", quest.get("id", "?"))
        if quest.get("done"):
            quest_line = f"{GREEN}Quest: {q_name} — DONE{RESET}  {DIM}/buddy:claim{RESET}"
        else:
            remaining = int(quest.get("remaining_s") or 0)
            mm, ss = divmod(remaining, 60)
            quest_line = f"{MAGENTA}Quest:{RESET} {q_name} {DIM}— {mm}m{ss:02d}s left{RESET}"
    else:
        quest_line = f"{DIM}Quest: idle  /buddy:quest{RESET}"

    # ── compose side-by-side ──
    # Right column: stats lines
    info_lines = [header, hp_line, mp_line, xp_line, "", stat1, stat2]
    if unspent_line:
        info_lines.append(unspent_line)
    info_lines.append("")
    info_lines.append(quest_line)

    # Pad sprite to uniform width
    sprite_w = 0
    if sprite_lines:
        sprite_w = max(len(l) for l in sprite_lines)
    gap = 3
    left_w = sprite_w + gap if sprite_lines else 0

    total_rows = max(len(sprite_lines), len(info_lines))
    for i in range(total_rows):
        sl = sprite_lines[i] if i < len(sprite_lines) else ""
        rl = info_lines[i] if i < len(info_lines) else ""
        if sprite_lines:
            padded_sprite = sl + " " * (left_w - len(sl))
            combined = padded_sprite + rl
        else:
            combined = rl
        lines.append(DIM + "│" + RESET + " " + combined + " " * max(0, box_w - 4 - _visible_len(combined)) + " " + DIM + "│" + RESET)

    # ── recent events ──
    recent = state.get("recent_events") or []
    if recent:
        lines.append(DIM + "│" + " " * (box_w - 2) + "│" + RESET)
        lines.append(DIM + _row(f"{DIM}Recent:{RESET}") + RESET)
        for ev in recent[-4:]:
            trunc = ev[:box_w - 8] if len(ev) > box_w - 8 else ev
            lines.append(DIM + _row(f"  {DIM}{trunc}{RESET}") + RESET)

    # ── footer ──
    lines.append(DIM + "│" + " " * (box_w - 2) + "│" + RESET)
    footer = f"{DIM}ctrl-C to quit{RESET}"
    lines.append(DIM + _row(footer) + RESET)
    lines.append(DIM + bot + RESET)

    return "\n".join(lines)


def _reset_terminal() -> None:
    sys.stdout.write(SHOW_CURSOR)
    sys.stdout.flush()


def _install_signal_handlers() -> None:
    def _handler(signum, frame):  # type: ignore[no-untyped-def]
        _reset_terminal()
        sys.exit(0)
    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def main() -> int:
    _install_signal_handlers()
    state_path = resolve_state_file()
    sprites_dir = _resolve_sprites_dir()
    frame_idx = 0
    try:
        sys.stdout.write(HIDE_CURSOR)
        while True:
            width = shutil.get_terminal_size(fallback=(64, 24)).columns
            state = _load_state(state_path) if state_path else None
            sys.stdout.write(CLEAR_SCREEN)
            sys.stdout.write(
                _render(state, state_path, width, frame_idx, sprites_dir)
            )
            sys.stdout.write("\n")
            sys.stdout.flush()
            frame_idx += 1
            time.sleep(REFRESH_SECONDS)
    finally:
        _reset_terminal()


if __name__ == "__main__":
    sys.exit(main())
