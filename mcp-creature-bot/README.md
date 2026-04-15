# mcp-creature-bot

An RPG buddy for Claude Code. A Pokemon-style ASCII creature lives in a tmux sidecar pane, gains XP every time you submit a prompt, levels up, and can be sent on simulated background quests.

**Unix + tmux required.** No Windows support.

## What you get

- A sidecar tmux pane showing your buddy (sprite, HP/XP bars, active quest)
- XP on every turn based on tokens consumed (scales with output tokens, cache reads are free, streak bonus for consecutive turns)
- Level-ups grant stat points you allocate yourself
- Starter roster of 24 beginner animals (rabbit, ant, axolotl, baby gecko, and friends) across six kinds (beast, insect, aquatic, amphibian, reptile, avian); `list_species` rolls a fresh random trio each call
- Each starter evolves at level 5 into one of two stronger natural forms based on the player's dominant stat (atk-focused rabbits become hares; def-focused rabbits become lop rabbits, etc.)
- Five zones of quests (Meadow → Forest → Cave → Ruins → Peaks) with 15 themed quests total; pick a zone and the buddy smart-picks a quest based on its stats
- Compact statusLine fallback for when you're not in tmux

## Install

End users: `brew install pgarfagnoli/buddy/mcp-creature-bot` (see the repo root README for tap instructions).

For development from source, two commands from this subfolder:

```bash
cd mcp-creature-bot
pip install --user -e .
mcp-creature-bot-install
```

The first installs the Python package into your user site-packages (editable, so source edits take effect immediately). The second wires everything up at user scope — no need to open Claude inside any particular directory:

- registers the MCP server with `claude mcp add --scope user`
- copies the `/buddy*` slash commands into `~/.claude/commands/`
- merges Stop / SessionStart / SessionEnd hooks into `~/.claude/settings.json`
- installs the compact buddy statusLine

Running `mcp-creature-bot-install` a second time is a no-op — the installer is idempotent.

## Use it

```bash
# in any terminal, from any directory
tmux new -s dev
cd /path/to/your/project
claude
```

Then in Claude Code — either use the slash commands or just ask in natural language ("start my buddy", "check my buddy's status", "send them on a forest quest"). Claude will call the right MCP tool.

- `/buddy` — see status (auto-spawns the sidecar pane if not running; first time: pick a starter)
- `/buddy start` — spawn the sidecar tmux pane (only works inside a tmux session)
- `/buddy stop` — close the pane
- `/buddy refresh` — stop and respawn the pane (e.g. to pick up new render code)
- `/buddy allocate atk 2 def 1` — spend stat points
- `/buddy quest` — list/start a quest
- `/buddy claim` — collect quest rewards
- `/buddy rename <name>`
- `/buddy uninstall` — wipe state

**Note on slash commands**: Claude Code discovers `~/.claude/commands/*.md` at session startup. If you run `mcp-creature-bot-install` mid-session, restart Claude Code to pick the new commands up — or just say "start my buddy" in plain English and Claude will call the `start_pane` MCP tool directly.

## How the pieces fit

```
┌─────────────────────────────────────────────────────┐
│  Claude Code session                                │
│  ┌─────────────────────┬──────────────────────────┐ │
│  │                     │                          │ │
│  │  claude pane        │  buddy pane (pane.py)    │ │
│  │                     │  reads state every 1s,   │ │
│  │                     │  renders ASCII art       │ │
│  └─────────────────────┴──────────────────────────┘ │
│    ↑                                 ↑              │
│    │                                 │              │
│    │ Stop hook (end of turn)         │ load_state() │
│    │ → sum tokens from transcript    │  + drain     │
│    │ → append to xp.log              │              │
│    ↓                                 │              │
│  ~/.claude/mcp-creature-bot/         │              │
│    xp.log  (queue)  ────drain────→  state.json      │
│                          (MCP server tool calls)    │
└─────────────────────────────────────────────────────┘
```

- **`xp.log`** is an append-only event queue. The Stop hook appends one JSON line per turn with summed token usage from the transcript. It never touches state.json.
- **`state.json`** is mutated by both the MCP server (on tool calls) and the sidecar pane (on each 1 Hz tick that finds pending events), always inside an exclusive flock + atomic rename. XP appears in the pane within ~1s of a turn ending.
- **`panes.json`** tracks the per-repo sidecar pane with refcounting, so multiple Claude sessions in the same repo share one pane.

## Uninstall

```bash
mcp-creature-bot-uninstall
pip uninstall mcp-creature-bot
```

`mcp-creature-bot-uninstall` deregisters the user-scope MCP server, removes the `/buddy*` commands from `~/.claude/commands/`, strips the hooks and statusLine from `~/.claude/settings.json`, kills any running sidecar panes, and deletes state under `~/.claude/mcp-creature-bot/`. User-edited command files are left alone. The second command removes the Python package itself.

## Notes

- XP formula: `max(1, output_tokens/50) + min((input + cache_creation)/500, 20)`; `+5` streak bonus if previous turn <30 min ago. Cache reads don't count.
- Level curve: `xp_to_next(L) = round(50 * L^1.5)`
- Quest results are rolled at claim time, not start time — the pane is pure display
- Quest timers use absolute epoch, so laptop sleep doesn't break anything
