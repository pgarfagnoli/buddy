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
/plugin marketplace add pgarfagnoli/buddy
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
| `/buddy:migrate` | One-shot cleanup of v0.3.x artifacts (see Migrating section) |

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
/plugin uninstall buddy --keep-data     # your buddy's level/XP/quests survive a reinstall
/plugin uninstall buddy                 # ⚠️  default: wipes state too
```

**Default behaviour is destructive.** Claude Code removes the hooks, the MCP registration, the skills, **and the plugin's persistent data directory** (`~/.claude/plugins/data/buddy/` — that's where `state.json`, `xp.log`, and your buddy's everything live). Pass `--keep-data` if you might reinstall later and want your Lv-*n* creature back.

If you started on v0.4.0 fresh, your *only* state is in `$CLAUDE_PLUGIN_DATA` — no backup anywhere. If you upgraded from v0.3.x, a snapshot-at-migration-time still sits at `~/.claude/buddy/` (untouched by `/buddy:migrate`), so a reinstall would re-migrate from that baseline — but any progress earned after the upgrade is plugin-only and lost without `--keep-data`.

## Migrating from v0.3.x (Homebrew era)

If you installed buddy via `brew install buddy` before v0.4.0, the full upgrade is three slash-commands inside Claude Code:

```
/plugin marketplace add pgarfagnoli/buddy
/plugin install buddy
/buddy:migrate
```

Or, equivalently, once the plugin is installed, tell Claude in plain English: *"migrate my old buddy install and uninstall the deprecated homebrew package."* The `/buddy:migrate` skill covers both halves.

What each step does:

- **`/plugin install buddy`** — Claude Code registers the new hooks, MCP server, and skills declaratively. Your Lv-*n* creature is copied from `~/.claude/buddy/state.json` into `~/.claude/plugins/data/buddy/` on first run, preserved end-to-end.
- **`/buddy:migrate`** runs in two phases:
  1. **`run_migration` MCP tool** — backs up `~/.claude/settings.json` to `.bak.<epoch>.pre-v0.4.0-migrate`, then strips: hook entries whose command contains `buddy.hooks.*` or `mcp_creature_bot.hooks.*`; the old statusLine if it pointed at `buddy.scripts.statusline`; any user-scope MCP server registration for `buddy`/`mcp-creature-bot`; shipped `/buddy*` files in `~/.claude/commands/`. User-edited files are left alone. Idempotent via a marker in the plugin data dir.
  2. **Homebrew cleanup** — the skill checks `brew list buddy` and `brew tap`; if either still shows the old install, it asks for your confirmation and runs `brew uninstall buddy` + `brew untap pgarfagnoli/buddy` (and `pgarfagnoli/homebrew-buddy` for the pre-rename tap name). You approve each Bash call.

A dry run precedes any mutation — you see the exact report before anything changes. After the migration completes, restart Claude Code so the stripped hooks stop firing in the current session.

If you skip `/buddy:migrate` entirely, your buddy still works (the plugin's hooks supersede the old ones for dispatch), but Claude Code logs `ModuleNotFoundError: No module named 'buddy'` every session as the legacy hooks keep firing harmlessly. The plugin's SessionStart hook nudges you each time you open Claude.

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
