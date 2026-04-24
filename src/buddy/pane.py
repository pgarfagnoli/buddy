"""Tmux sidecar pane renderer.

Invoked by /buddy start as:
    tmux split-window -h -l 32 -d 'python -m buddy.pane'

Runs a 1 Hz loop: reads state, redraws the full pane in alternate screen mode.
Exits cleanly on SIGTERM/SIGINT.
"""
from __future__ import annotations

import os
import random
import shutil
import signal
import sys
import textwrap
import time
import traceback
from typing import Optional

from . import combat, leveling, paths, personalities, quests, skills, species, vignettes
from .state import State, drain_xp_log, load_state, mutate_state

_LOGGED_EXC_SIGS: set[str] = set()


def _log_pane_exception(ctx: str, exc: BaseException) -> None:
    """Append a deduped traceback to ~/.claude/buddy/pane.log.

    Dedupes by (context, exception type, exception message) so a recurring
    per-tick error logs once per pane lifetime instead of spamming the file.
    Must never itself raise — the pane relies on this helper to stay alive.
    """
    sig = f"{ctx}:{type(exc).__name__}:{exc}"
    if sig in _LOGGED_EXC_SIGS:
        return
    _LOGGED_EXC_SIGS.add(sig)
    try:
        log_path = paths.root() / "pane.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {ctx}\n")
            f.write(traceback.format_exc())
            f.write("\n")
    except Exception:
        pass

TICK_HZ = 1.0
BAR_WIDTH = 14
FLAVOR_CHANCE = 0.15
COMBAT_POSE_HOLD_S = 1.2  # how long a strike holds its attack/hurt pose
IDLE_VIGNETTE_PERIOD_S = 25  # rotate the under-sprite vignette this often when idle

# ANSI
CSI = "\x1b["
ALT_ON = CSI + "?1049h"
ALT_OFF = CSI + "?1049l"
CURSOR_HOME = CSI + "H"
CLEAR_SCREEN = CSI + "2J"
HIDE_CURSOR = CSI + "?25l"
SHOW_CURSOR = CSI + "?25h"
RESET = CSI + "0m"
BOLD = CSI + "1m"
DIM = CSI + "2m"
FG_RED = CSI + "31m"
FG_GREEN = CSI + "32m"
FG_YELLOW = CSI + "33m"
FG_BLUE = CSI + "34m"
FG_MAGENTA = CSI + "35m"
FG_CYAN = CSI + "36m"
FG_BRIGHT_GREEN = CSI + "92m"
FG_BRIGHT_CYAN = CSI + "96m"

KIND_COLOR = {
    "fire": FG_RED, "water": FG_CYAN, "normal": FG_YELLOW,
    "beast": FG_YELLOW, "insect": FG_GREEN, "aquatic": FG_BLUE, "avian": FG_MAGENTA,
    "amphibian": FG_BRIGHT_CYAN, "reptile": FG_BRIGHT_GREEN,
}


def _term_size() -> tuple[int, int]:
    try:
        cols, rows = shutil.get_terminal_size((32, 20))
    except OSError:
        cols, rows = 32, 20
    return cols, rows


def _bar(current: int, maximum: int, width: int = BAR_WIDTH, color: str = FG_GREEN) -> str:
    if maximum <= 0:
        filled = 0
    else:
        filled = int(round(width * current / maximum))
    filled = max(0, min(width, filled))
    return color + "█" * filled + DIM + "░" * (width - filled) + RESET


def _fmt_duration(seconds: int) -> str:
    m, s = divmod(max(0, seconds), 60)
    return f"{m:d}:{s:02d}"


def _wrap_plain(text: str, width: int) -> list[str]:
    """Wrap plain (no-ANSI) text to `width`, returning at least one line."""
    if width <= 0:
        return [text]
    lines = textwrap.wrap(
        text,
        width=width,
        break_long_words=True,
        break_on_hyphens=True,
    )
    return lines or [text]


def _combat_poses(now: float, last_round_at: int, last_attacker: Optional[str]) -> tuple[str, str]:
    """Return (buddy_pose, enemy_pose) where each is 'idle', 'attack', or 'hurt'.

    During the COMBAT_POSE_HOLD_S window after the most recent round, the
    attacker shows in attack pose and the defender in hurt pose. Outside
    that window, both return to idle.
    """
    if last_attacker is None or now - last_round_at > COMBAT_POSE_HOLD_S:
        return "idle", "idle"
    if last_attacker == "buddy":
        return "attack", "hurt"
    if last_attacker == "enemy":
        return "hurt", "attack"
    return "idle", "idle"


def _pick_pose_frame(
    pose: str,
    idle: list[list[str]] | tuple[tuple[str, ...], ...],
    attack: list[list[str]] | tuple[tuple[str, ...], ...],
    hurt: list[list[str]] | tuple[tuple[str, ...], ...],
    tick: int,
) -> list[str]:
    """Pick one frame from the matching bank, falling back to idle if the
    requested bank is empty.
    """
    bank = idle
    if pose == "attack" and attack:
        bank = attack
    elif pose == "hurt" and hurt:
        bank = hurt
    if not bank:
        return [""]
    frame = bank[(tick // 2) % len(bank)]
    return list(frame)


def _side_by_side(left: list[str], right: list[str], gap: int = 2) -> list[str]:
    """Stack two ASCII frames side-by-side, padding the shorter one to match."""
    h = max(len(left), len(right))
    lw = max((len(line) for line in left), default=0)
    out: list[str] = []
    for i in range(h):
        l = left[i] if i < len(left) else ""
        r = right[i] if i < len(right) else ""
        out.append(l.ljust(lw) + " " * gap + r)
    return out


class FlavorTicker:
    def __init__(self, capacity: int = 5) -> None:
        self.lines: list[str] = []
        self.capacity = capacity
        self.rng = random.Random()
        self.idle_vignette: str = ""
        self.idle_vignette_at: float = 0.0

    def maybe_tick(self, state: State) -> None:
        b = state.buddy
        if b is None:
            return
        if b.quest is not None:
            # Mid-quest flavor: chance-gated draw from the quest's flavor pool.
            if self.rng.random() > FLAVOR_CHANCE:
                return
            try:
                line = quests.pick_flavor_line(b.quest.id, b.name, self.rng)
            except Exception as exc:
                _log_pane_exception("ticker.pick_flavor_line", exc)
                return
            self.push(line)
            return
        # Idle: rotate a vignette from the trait-weighted pool every
        # IDLE_VIGNETTE_PERIOD_S seconds. Decoupled from the activity loop.
        now = time.time()
        if now - self.idle_vignette_at < IDLE_VIGNETTE_PERIOD_S:
            return
        try:
            v = vignettes.pick(b, self.rng)
            self.idle_vignette = vignettes.render(v, b)
            self.idle_vignette_at = now
        except Exception as exc:
            _log_pane_exception("ticker.idle_vignette", exc)

    def push(self, line: str) -> None:
        self.lines.append(line)
        if len(self.lines) > self.capacity:
            self.lines = self.lines[-self.capacity:]


def _render(state: State, ticker: FlavorTicker, tick: int, cols: int, rows: int) -> str:
    out: list[str] = []
    out.append(CURSOR_HOME + CLEAR_SCREEN)
    out.append(BOLD + FG_MAGENTA + "─── buddy ".ljust(cols, "─") + RESET + "\n\n")

    if state.buddy is None:
        out.append(DIM + "  no buddy yet" + RESET + "\n")
        out.append(DIM + "  use /buddy to" + RESET + "\n")
        out.append(DIM + "  pick a starter" + RESET + "\n")
        return "".join(out)

    b = state.buddy
    sp = species.get(b.species)
    color = KIND_COLOR.get(sp.kind, FG_YELLOW)

    # sprite: cycle through N frames at 2s each. When on an in-progress
    # quest, prefer the species's own motion bank, then fall back to the
    # shared "away" frames, then to the species idle frames.
    # In combat: render buddy + enemy side-by-side with attack/hurt poses
    # that flash for COMBAT_POSE_HOLD_S after each round.
    if b.combat is not None:
        try:
            enemy = combat.get_enemy(b.combat.enemy_id)
            esprite = combat.get_enemy_sprite(b.combat.enemy_id)
            buddy_pose, enemy_pose = _combat_poses(
                time.time(), b.combat.last_round_at, b.combat.last_attacker,
            )
            buddy_frame = _pick_pose_frame(
                buddy_pose,
                species.sprite_frames(b.species),
                species.attack_frames(b.species),
                species.hurt_frames(b.species),
                tick,
            )
            enemy_frame = _pick_pose_frame(
                enemy_pose, esprite.idle, esprite.attack, esprite.hurt, tick,
            )
            stacked = _side_by_side(buddy_frame, enemy_frame, gap=3)
            ecolor = FG_RED
            for line in stacked:
                out.append("  " + color + line + RESET + "\n")
            # Inline label row right under the sprites.
            buddy_label = b.name
            enemy_label = enemy.name
            label_left = buddy_label.ljust(max(
                (len(line) for line in buddy_frame), default=0
            ))
            out.append(
                "  " + color + label_left + RESET
                + "   " + ecolor + enemy_label + RESET + "\n"
            )
            out.append("\n")
        except Exception as exc:
            _log_pane_exception("render.combat_sprites", exc)
            # Fall back to the plain buddy sprite if anything goes wrong.
            for line in species.sprite_frames(b.species)[0]:
                out.append("  " + color + line + RESET + "\n")
            out.append("\n")
    else:
        if b.quest is not None and b.quest.remaining() > 0:
            own_motion = species.species_motion_frames(b.species)
            if own_motion:
                frames = own_motion
            else:
                shared = species.quest_sprite_frames()
                frames = shared if shared else species.sprite_frames(b.species)
        else:
            frames = species.sprite_frames(b.species)
        frame_idx = (tick // 2) % max(1, len(frames))
        for line in frames[frame_idx]:
            out.append("  " + color + line + RESET + "\n")
        out.append("\n")

        # Idle vignette — render under the sprite when the buddy is idle
        # (no active quest). The pane's FlavorTicker rotates a fresh vignette
        # every IDLE_VIGNETTE_PERIOD_S seconds; b.idle_flavor (written by the
        # activity loop on its slow tick) is the persistent fallback that
        # covers the first ~25s after a fresh pane spawn.
        if b.quest is None:
            flavor = ticker.idle_vignette or b.idle_flavor
            if flavor:
                for piece in _wrap_plain(flavor, max(1, cols - 2)):
                    out.append(f"  {DIM}{FG_CYAN}{piece}{RESET}\n")
                out.append("\n")

    # Pre-compute branch eligibility once — used for both the ✨ flash
    # next to the level and the EVOLVE notice block below the name.
    if sp.evolves_at is not None and sp.evolutions:
        evo_branches = [species.branch_eligibility(e, b.stats) for e in sp.evolutions]
    else:
        evo_branches = []
    at_or_past_evolve = sp.evolves_at is not None and b.level >= sp.evolves_at
    any_eligible = any(br["eligible"] for br in evo_branches)

    # name + level
    stat_flash = (BOLD + FG_YELLOW + " ⚡" + str(b.stat_points_unspent) + RESET) if b.stat_points_unspent else ""
    evo_flash = ""
    if at_or_past_evolve and any_eligible:
        evo_flash = BOLD + FG_CYAN + " ✨" + RESET
    mythic_flash = BOLD + FG_MAGENTA + " ★" + RESET if b.mythic else ""
    out.append(f"  {BOLD}{b.name}{RESET}  Lv{b.level}{stat_flash}{evo_flash}{mythic_flash}\n")
    display_name = b.mythic.display_name if b.mythic else sp.display_name
    personality_def = personalities.PERSONALITIES.get(b.personality)
    display_plain = display_name
    if personality_def:
        display_plain = f"{display_name}  ({personality_def.display_name})"
    display_budget = max(1, cols - 2)
    for piece in _wrap_plain(display_plain, display_budget):
        out.append(f"  {DIM}{piece}{RESET}\n")
    out.append("\n")

    # EVOLVE block — only while at or past the evolve level. Each branch
    # renders with ✓/✗ per requirement so the player can see exactly what's
    # blocking them.
    if at_or_past_evolve and evo_branches:
        out.append(f"  {BOLD}EVOLVE{RESET}\n")
        name_w = max(len(br["display_name"]) for br in evo_branches)
        for br in evo_branches:
            prefix = (FG_CYAN + "✨" + RESET) if br["eligible"] else "  "
            check_parts: list[str] = []
            for c in br["checks"]:
                tick = (FG_GREEN + "✓" + RESET) if c["met"] else (FG_RED + "✗" + RESET)
                check_parts.append(f"{tick} {c['stat']} {c['actual']}/{c['required']}")
            checks_text = "  ".join(check_parts)
            name_text = br["display_name"].ljust(name_w)
            name_colored = (
                f"{FG_CYAN}{name_text}{RESET}" if br["eligible"] else f"{DIM}{name_text}{RESET}"
            )
            out.append(f"  {prefix} {name_colored}  {checks_text}\n")
        out.append("\n")

    # Status bars, two per row
    bar_w = 10
    xp_cap = leveling.xp_to_next(b.level, species.get_tier(b.species), sp.evolves_at)
    cells: list[tuple[str, str]] = []
    for label, cur, maximum, color in (
        ("HP", b.current_hp, b.max_hp, FG_RED),
        ("MP", b.current_mana, b.max_mana, FG_BLUE),
        ("MD", b.mood, b.max_mood, FG_MAGENTA),
        ("ST", b.stamina, b.max_stamina, FG_CYAN),
        ("XP", b.xp, xp_cap, FG_GREEN),
    ):
        bar = _bar(cur, maximum, width=bar_w, color=color)
        val_text = f"{cur}/{maximum}"
        visible_w = 3 + bar_w  # "HP " + bar
        top = f"{label} {bar}"
        val = f"   {DIM}{val_text}{RESET}" + " " * max(0, visible_w - 3 - len(val_text))
        cells.append((top, val))
    gap = "  "
    empty_top = " " * (3 + bar_w)
    for i in range(0, len(cells), 2):
        left_top, left_val = cells[i]
        right_top, right_val = cells[i + 1] if i + 1 < len(cells) else (empty_top, empty_top)
        out.append(f"  {left_top}{gap}{right_top}\n")
        out.append(f"  {left_val}{gap}{right_val}\n")
    out.append("\n")

    s = b.stats
    out.append(f"  {DIM}ATK{RESET} {s.atk:<3} {DIM}DEF{RESET} {s.def_:<3}\n")
    out.append(f"  {DIM}SPD{RESET} {s.spd:<3} {DIM}LCK{RESET} {s.luck:<3}\n")
    out.append(f"  {DIM}INT{RESET} {s.int_:<3} {DIM}RES{RESET} {s.res:<3}\n")
    # Active skills — dim if mana can't cover the cost.
    if b.active_skills:
        out.append(f"\n  {BOLD}SKILLS{RESET}\n")
        for sid in b.active_skills:
            try:
                sk = skills.get(sid)
            except KeyError:
                continue
            if b.current_mana < sk.mana_cost:
                out.append(f"  {DIM}{sk.name} ({sk.mana_cost} MP){RESET}\n")
            else:
                out.append(f"  {FG_BLUE}{sk.name}{RESET} {DIM}({sk.mana_cost} MP){RESET}\n")
    out.append("\n")

    # quest
    if b.quest:
        try:
            qdef = quests.get(b.quest.id)
            remaining = b.quest.remaining()
            header_budget = max(1, cols - 4)
            if remaining > 0:
                spinner = "|/-\\"[tick % 4]
                wrapped_name = _wrap_plain(qdef.name, header_budget)
                out.append(f"  {BOLD}{FG_CYAN}{spinner} {wrapped_name[0]}{RESET}\n")
                for piece in wrapped_name[1:]:
                    out.append(f"    {BOLD}{FG_CYAN}{piece}{RESET}\n")
                out.append(f"  {DIM}time left: {_fmt_duration(remaining)}{RESET}\n\n")
            else:
                wrapped_name = _wrap_plain(qdef.name, header_budget)
                out.append(f"  {BOLD}{FG_GREEN}✓ {wrapped_name[0]}{RESET}\n")
                for piece in wrapped_name[1:]:
                    out.append(f"    {BOLD}{FG_GREEN}{piece}{RESET}\n")
                out.append(f"  {BOLD}{FG_GREEN}  done!{RESET}\n")
                out.append(f"  {DIM}/buddy claim to{RESET}\n")
                out.append(f"  {DIM}collect reward{RESET}\n\n")
            flavor_budget = max(1, cols - 4)
            if b.combat is not None:
                try:
                    enemy = combat.get_enemy(b.combat.enemy_id)
                    ebar = _bar(b.combat.enemy_hp, b.combat.enemy_max_hp, width=10, color=FG_RED)
                    out.append(
                        f"  {BOLD}{FG_RED}⚔ {enemy.glyph} {enemy.name}{RESET}\n"
                    )
                    out.append(
                        f"  HP {ebar} {DIM}{b.combat.enemy_hp}/{b.combat.enemy_max_hp}{RESET}\n\n"
                    )
                    for line in b.combat.log[-4:]:
                        for i, piece in enumerate(_wrap_plain(line, flavor_budget)):
                            marker = "· " if i == 0 else "  "
                            out.append(f"  {DIM}{marker}{piece}{RESET}\n")
                except KeyError:
                    out.append(f"  {DIM}· combat underway{RESET}\n")
            else:
                if qdef.category == "combat" and qdef.hp_penalty_pct_on_failure > 0:
                    out.append(f"  {DIM}· scouting for trouble…{RESET}\n")
                for line in ticker.lines[-3:]:
                    wrapped = _wrap_plain(line, flavor_budget)
                    for i, piece in enumerate(wrapped):
                        marker = "· " if i == 0 else "  "
                        out.append(f"  {DIM}{marker}{piece}{RESET}\n")
        except Exception as exc:
            _log_pane_exception("render.quest", exc)
            remaining = b.quest.remaining()
            out.append(f"  {DIM}quest in progress{RESET}\n")
            if remaining > 0:
                out.append(f"  {DIM}time left: {_fmt_duration(remaining)}{RESET}\n\n")
            else:
                out.append(f"  {DIM}/buddy claim{RESET}\n\n")
    else:
        out.append(f"  {DIM}idle — try /buddy quest{RESET}\n\n")

    # recent events (level-ups, etc.)
    if state.recent_events:
        out.append("\n" + DIM + "─── log ".ljust(cols, "─") + RESET + "\n")
        event_budget = max(1, cols - 2)
        for line in state.recent_events[-2:]:
            for piece in _wrap_plain(line, event_budget):
                out.append(f"  {DIM}{piece}{RESET}\n")

    return "".join(out)


def _sigterm_handler(signum, frame):  # noqa: ARG001
    sys.stdout.write(RESET + SHOW_CURSOR + ALT_OFF)
    sys.stdout.flush()
    sys.exit(0)


def _tick_state(rng: random.Random) -> State:
    """Single-pass pane tick: drain XP events, advance combat, return state.

    Optimized to minimize flock acquisitions:
    - If no XP events AND combat is in WAITING (strike interval not elapsed),
      skip the exclusive flock entirely and return a read-only state snapshot.
    - Otherwise, batch drain + combat into one mutate_state call.
    """
    events = drain_xp_log()

    # Fast path: if nothing to drain, check if we can skip the flock.
    if not events:
        try:
            state = load_state()
        except Exception:
            return State()
        b = state.buddy
        if b is None or b.quest is None:
            return state  # idle — nothing to mutate
        if b.combat is not None:
            # Combat active — check if either side is ready to strike.
            now = int(time.time())
            buddy_ready = (
                b.combat.next_buddy_strike_at == 0
                or now >= b.combat.next_buddy_strike_at
            )
            enemy_ready = (
                b.combat.next_enemy_strike_at == 0
                or now >= b.combat.next_enemy_strike_at
            )
            if not buddy_ready and not enemy_ready:
                return state  # WAITING — skip flock, no mutation needed

    # Slow path: something needs mutating. Single flock for everything.
    def fn(state: State) -> None:
        if events:
            leveling.apply_xp_events(state, events)
        b = state.buddy
        if b is None or b.quest is None:
            return
        try:
            qdef = quests.get(b.quest.id)
        except KeyError:
            return
        now = int(time.time())
        if b.combat is None:
            if qdef.category == "combat":
                skills.try_out_of_combat_regen(b)
            spawned = combat.try_spawn(b, qdef, now, rng)
            if spawned and b.combat is not None:
                try:
                    enemy_name = combat.get_enemy(b.combat.enemy_id).name
                    state.add_event(f"{b.name} engages a {enemy_name}!")
                except KeyError:
                    pass
            return
        prev_enemy_id = b.combat.enemy_id
        prev_xp = b.xp
        result = combat.tick_encounter(b, qdef, now, rng)
        if result == combat.TickResult.BUDDY_WIN:
            try:
                enemy_name = combat.get_enemy(prev_enemy_id).name
                gained = b.xp - prev_xp
                state.add_event(f"{b.name} defeats the {enemy_name} (+{gained} xp)")
                leveling.check_level_ups(state)
            except KeyError:
                pass
            return
        if result == combat.TickResult.ONGOING and b.combat is None:
            try:
                enemy_name = combat.get_enemy(prev_enemy_id).name
                state.add_event(f"{b.name} slips away from the {enemy_name}")
            except KeyError:
                pass
            return
        if result == combat.TickResult.BUDDY_DOWN:
            try:
                res = quests.fail_from_combat(b, rng)
            except ValueError:
                return
            fired_names: list[str] = []
            for sid in res.fired_skills:
                try:
                    fired_names.append(skills.get(sid).name)
                except KeyError:
                    fired_names.append(sid)
            state.add_event(quests.format_claim_event_line(res, fired_names))
            leveling.check_level_ups(state)
    try:
        return mutate_state(fn)
    except Exception as exc:
        _log_pane_exception("tick_state", exc)
        try:
            return load_state()
        except Exception:
            return State()


def _state_signature(state: State) -> Optional[tuple]:
    """Cheap fingerprint of the fields that affect render output.
    Returns None if no buddy (always rebuild).
    """
    b = state.buddy
    if b is None:
        return None
    return (
        b.current_hp, b.current_mana, b.xp, b.mood, b.stamina,
        b.quest.id if b.quest else None,
        b.quest.remaining() if b.quest else None,
        b.combat.enemy_hp if b.combat else None,
        b.combat.last_attacker if b.combat else None,
        b.idle_flavor,
        b.stat_points_unspent,
    )


def main() -> int:
    signal.signal(signal.SIGTERM, _sigterm_handler)
    signal.signal(signal.SIGINT, _sigterm_handler)

    if not sys.stdout.isatty():
        print("pane.py requires a TTY (run inside tmux split-window)", file=sys.stderr)
        return 2

    sys.stdout.write(ALT_ON + HIDE_CURSOR + CLEAR_SCREEN)
    sys.stdout.flush()

    ticker = FlavorTicker()
    tick = 0
    last_sig: Optional[tuple] = None
    last_frame = ""
    try:
        while True:
            try:
                state = _tick_state(ticker.rng)
                cols, rows = _term_size()
                ticker.maybe_tick(state)
                # Render cache: skip rebuild if state hasn't changed,
                # but force every 2 ticks for sprite animation cycling.
                sig = _state_signature(state)
                if sig != last_sig or tick % 2 == 0:
                    frame = _render(state, ticker, tick, cols, rows)
                    last_sig = sig
                    last_frame = frame
                else:
                    frame = last_frame
                sys.stdout.write(frame)
                sys.stdout.flush()
            except Exception as exc:
                _log_pane_exception("main_loop", exc)
            tick += 1
            # Adaptive tick: 1 Hz during quest/combat, 0.25 Hz when idle.
            # Reduces file I/O by 75% when nothing is happening. Vignette
            # rotation (25s period) still works — it checks wall clock.
            b = state.buddy
            if b and (b.quest or b.combat):
                time.sleep(1.0 / TICK_HZ)
            else:
                time.sleep(4.0)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(RESET + SHOW_CURSOR + ALT_OFF)
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
