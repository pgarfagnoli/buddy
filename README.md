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
/plugin uninstall buddy
```

Claude Code removes the hooks, the MCP registration, and the skills. State under `$CLAUDE_PLUGIN_DATA` (your buddy's level, XP, quest progress) is preserved by default; pass `--keep-data=false` to wipe it too.

## Migrating from v0.3.x (Homebrew era)

If you installed buddy via `brew install buddy` before v0.4.0, the upgrade is:

```bash
brew uninstall buddy
brew untap pgarfagnoli/buddy
```

Then inside Claude Code:

```
/plugin marketplace add pgarfagnoli/buddy
/plugin install buddy
/buddy:migrate
```

What each step does:

- **`brew uninstall buddy`** — removes the old Python package. Your data at `~/.claude/buddy/` is not touched.
- **`/plugin install buddy`** — installs the new plugin; Claude Code registers its hooks, MCP server, and skills declaratively. Your Lv-*n* creature is copied from `~/.claude/buddy/state.json` into `$CLAUDE_PLUGIN_DATA/` on first run — no manual import.
- **`/buddy:migrate`** — one-shot cleanup of v0.3.x leftovers in `~/.claude/settings.json` and `~/.claude/commands/`. Specifically:
  1. Backs up `~/.claude/settings.json` with a timestamped `.bak.<epoch>.pre-v0.4.0-migrate` suffix.
  2. Strips hook entries whose command contains `buddy.hooks.*` (or the even-older `mcp_creature_bot.hooks.*`).
  3. Removes the old statusLine if it pointed at `buddy.scripts.statusline`.
  4. Runs `claude mcp remove --scope user buddy` if the legacy user-scope MCP registration is still around.
  5. Deletes shipped `/buddy*` markdown files in `~/.claude/commands/` — but only those that still match their original content; anything you edited is left alone.
  6. Writes a marker in `$CLAUDE_PLUGIN_DATA` so subsequent invocations are no-ops.

`/buddy:migrate` runs a dry-run first and shows you what it would change — you confirm before it touches anything. If you skip this step, your buddy still works (the plugin's hooks supersede the old ones at the MCP-server-dispatch level), but Claude Code will log `ModuleNotFoundError: No module named 'buddy'` every session as the legacy hooks keep firing. The SessionStart nudge will remind you.

After a successful migration, restart Claude Code so the stripped hooks stop firing in the current session.

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
