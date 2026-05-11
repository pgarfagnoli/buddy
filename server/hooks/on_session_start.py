"""SessionStart hook: ensure state file exists and, on first run, nudge the
user to pick a starter. Emits stdout, which Claude Code surfaces as a system
reminder inside the session context.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

import state  # noqa: E402
import migrate  # noqa: E402


def _ensure_symlink(bin_dir: Path, name: str, plugin_root: str) -> None:
    """Symlink a buddy CLI into ~/.local/bin/ if not already current."""
    src = Path(plugin_root) / "bin" / name
    if not src.exists():
        return
    link = bin_dir / name
    if link.is_symlink() or link.exists():
        if link.is_symlink() and link.resolve() == src.resolve():
            return
        link.unlink()
    link.symlink_to(src)


def _ensure_bin_symlinks() -> None:
    """Symlink buddy-pane and buddy-statusline into ~/.local/bin/."""
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not plugin_root:
        return
    bin_dir = Path.home() / ".local" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    _ensure_symlink(bin_dir, "buddy-pane", plugin_root)
    _ensure_symlink(bin_dir, "buddy-statusline", plugin_root)
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    if str(bin_dir) not in path_dirs:
        print(
            f"buddy CLIs have been symlinked to {bin_dir}. "
            f"If the user cannot run `buddy-pane`, suggest they add "
            f"~/.local/bin to their PATH."
        )


_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
_NEW_STATUSLINE_MARKER = "buddy-statusline"


def _ensure_statusline() -> None:
    """Add statusLine config to ~/.claude/settings.json if not already set."""
    settings: dict = {}
    if _SETTINGS_PATH.exists():
        try:
            settings = json.loads(_SETTINGS_PATH.read_text())
        except (OSError, json.JSONDecodeError):
            return
    existing = settings.get("statusLine")
    if isinstance(existing, dict):
        cmd = str(existing.get("command", ""))
        if _NEW_STATUSLINE_MARKER in cmd:
            return
        if cmd:
            return
    bin_dir = Path.home() / ".local" / "bin"
    link = bin_dir / "buddy-statusline"
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    if str(bin_dir) in path_dirs:
        cmd = "buddy-statusline"
    else:
        cmd = str(link)
    settings["statusLine"] = {"command": cmd}
    try:
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_PATH.write_text(json.dumps(settings, indent=2) + "\n")
    except OSError:
        pass


def main() -> int:
    try:
        _ = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        pass
    try:
        _ensure_bin_symlinks()
    except Exception:
        pass
    try:
        _ensure_statusline()
    except Exception:
        pass
    try:
        state.init_state_if_missing()
        s = state.load_state()
    except Exception:
        return 0

    # If the user upgraded from the Homebrew/pip era, their settings.json and
    # ~/.claude/commands/ may still carry pre-v0.4.0 buddy entries. Nudge them
    # to run /buddy:migrate — exactly once. The nudge goes to stdout, which
    # Claude Code injects as a system reminder.
    try:
        if migrate.is_migration_needed():
            print(
                "buddy plugin: pre-v0.4.0 artifacts detected in ~/.claude/ "
                "(likely leftover hooks, statusLine, MCP registration, or "
                "/buddy* command files from a previous Homebrew install). "
                "Suggest the user run /buddy:migrate — it backs up settings.json "
                "and strips the stale entries."
            )
    except Exception:
        pass

    if s.buddy is None:
        print(
            "buddy is installed but no buddy has been chosen yet. "
            "If the user mentions their buddy, suggest they pick a starter — "
            "call the list_species tool, then choose_buddy with the chosen id "
            "and a name they like."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
