# buddy

A [Claude Code](https://docs.claude.com/en/docs/claude-code) plugin: a Pokemon-style RPG companion that gains XP every time your Claude session finishes a turn, levels up, learns skills, and can be sent on simulated background quests while you code.

```
    (\_/)
   ( •_•)    Lv 7   HP ████████░░
   / >🥕     XP ██████░░░░  on a Forest quest...
```

**Requires:** macOS or Linux, [Claude Code](https://docs.claude.com/en/docs/claude-code), and `python3` 3.10+ (standard on every modern macOS and Linux). No Homebrew, no tmux, no pip dependencies.

## Install

Inside a Claude Code session:

```
/plugin marketplace add pgarfagnoli/homebrew-buddy
/plugin install buddy
```

That's it. Claude Code copies the plugin into its cache, registers buddy's MCP server, wires the three lifecycle hooks (Stop / SessionStart / SessionEnd), and makes every `/buddy:*` slash command available.

## First run

Type `/buddy:start` in Claude Code. It rolls three random starter species and asks which you'd like + what name. Pick one, and you're running.

From then on, every prompt you finish earns XP. Level up, spend stat points, send your buddy on a quest, claim rewards.

## Playing

Slash commands are namespaced to the plugin:

| Command | What it does |
|---|---|
| `/buddy:status` | Show level, HP, MP, XP, stats, active quest, recent events |
| `/buddy:start` | Pick and name a starter |
| `/buddy:quest [zone]` | List zones or start a quest |
| `/buddy:claim` | Collect rewards when a quest finishes |
| `/buddy:allocate atk 2 def 1` | Spend unallocated stat points |
| `/buddy:skills` | Show known skills, equip an active loadout (≤4) |
| `/buddy:evolve` | Commit a species evolution (or a mythic, if eligible) |
| `/buddy:rename <name>` | Rename your buddy |

Or just ask Claude: *"how's my buddy?"*, *"send them on a cave quest"*, *"allocate 3 to attack"* — the skills handle routing.

## Standalone status pane

Buddy does not embed a live pane into Claude Code (plugins can't). Instead, the plugin exposes a `buddy-pane` CLI that you can run in **any second terminal** — a Terminal.app window, an iTerm split, a tmux pane, wezterm, kitty, whatever:

```bash
buddy-pane
```

It polls the buddy state every 2 seconds and repaints a compact HP / MP / XP / quest view in place. Ctrl-C to quit.

(Available on your PATH when the plugin is enabled — Claude Code adds the plugin's `bin/` dir to the shell env.)

## Uninstall

```
/plugin uninstall buddy
```

Claude Code removes the hooks, the MCP registration, and the skills. State under `$CLAUDE_PLUGIN_DATA` (your buddy's level, XP, quest progress) is preserved by default; pass `--keep-data=false` to wipe it too.

## Migrating from v0.3.x (Homebrew era)

If you installed buddy via `brew install buddy` before v0.4.0:

```bash
# 1. Clean up the old hand-patched settings.json + MCP registration.
buddy-uninstall

# 2. Remove the Homebrew package and tap — they're no longer needed.
brew uninstall buddy
brew untap pgarfagnoli/buddy
```

Then inside Claude Code:

```
/plugin marketplace add pgarfagnoli/homebrew-buddy
/plugin install buddy
```

Your creature's state (`~/.claude/buddy/state.json`) is copied into the plugin's data dir automatically on first run; your Lv-*n* buddy comes along for the ride.

## Repository layout

```
buddy/
├── .claude-plugin/
│   ├── plugin.json          ← manifest (name, version, author)
│   └── marketplace.json     ← marketplace entry
├── skills/                  ← one skill per /buddy:<name> command
├── hooks/hooks.json         ← Stop / SessionStart / SessionEnd wiring
├── .mcp.json                ← stdio MCP server declaration
├── bin/
│   └── buddy-pane           ← standalone status pane CLI
├── server/                  ← Python server + game logic (stdlib only)
│   ├── main.py              ← stdio entry
│   ├── mini_mcp.py          ← ~150-line hand-rolled MCP subset
│   ├── tools.py             ← 16 @mcp.tool() handlers
│   ├── hooks/               ← Stop / SessionStart / SessionEnd scripts
│   ├── pane.py              ← buddy-pane renderer
│   └── …                    ← state, leveling, quests, combat, skills, species, …
└── data/sprites/            ← ASCII sprite assets
```
