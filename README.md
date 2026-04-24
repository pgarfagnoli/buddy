# buddy

An RPG buddy for [Claude Code](https://docs.claude.com/en/docs/claude-code). A Pokemon-style ASCII creature lives in a tmux sidecar pane next to your Claude session, gains XP every time you submit a prompt, levels up, and can be sent on simulated background quests while you code.

```
    (\_/)
   ( •_•)    Lv 7   HP ████████░░
   / >🥕     XP ██████░░░░  on a Forest quest...
```

**Requires:** macOS or Linux, [tmux](https://github.com/tmux/tmux), and [Claude Code](https://docs.claude.com/en/docs/claude-code). No Windows support.

## Install

```bash
brew tap pgarfagnoli/buddy
brew install buddy
buddy-install
```

What each step does:

1. `brew tap` — points Homebrew at this repo.
2. `brew install buddy` — installs the Python package, its CLI entry points, and `tmux` if you don't already have it.
3. `buddy-install` — wires buddy into Claude Code at user scope: registers the MCP server, drops `/buddy*` slash commands into `~/.claude/commands/`, merges hooks into `~/.claude/settings.json`, and installs the statusLine. Idempotent — safe to re-run.

If Claude Code is already open, restart it so it picks up the new slash commands and hooks.

## First run

```bash
tmux new -s dev          # buddy needs a tmux session
cd ~/your-project
claude                   # start Claude Code as usual
```

Then in Claude, just say:

> start my buddy

Claude calls the right tool, a sidecar pane opens on the right, and you'll be prompted to pick a starter from a rolled trio (rabbit, axolotl, baby gecko, and friends — 24 total across 6 kinds).

From there, every prompt you send earns XP. Level up, allocate stat points, send them on quests. That's it.

## Playing

You can use slash commands or natural language — Claude will route either to the right MCP tool.

| Slash command | What it does |
|---|---|
| `/buddy` | Show status (spawns the pane if it isn't running) |
| `/buddy start` / `stop` / `refresh` | Control the sidecar pane |
| `/buddy allocate atk 2 def 1` | Spend stat points after leveling |
| `/buddy quest` | List zones and start a quest |
| `/buddy claim` | Collect rewards when a quest finishes |
| `/buddy rename <name>` | Rename your buddy |
| `/buddy uninstall` | Wipe local state |

Or just ask: *"how's my buddy?"*, *"send them on a cave quest"*, *"allocate 3 points to attack"*.

## Uninstall

```bash
buddy-uninstall          # unregister MCP, remove commands, hooks, statusLine, state
brew uninstall buddy     # remove the Python package
brew untap pgarfagnoli/buddy
```

## Learn more

- **[DEVELOPMENT.md](./DEVELOPMENT.md)** — full feature list, architecture, XP/level formulas, developer/editable-install flow
- **[Formula/buddy.rb](./Formula/buddy.rb)** — the Homebrew formula

## Repository layout

```
homebrew-buddy/
├── Formula/
│   └── buddy.rb        ← Homebrew formula
├── src/buddy/          ← Python package source
├── pyproject.toml
├── README.md
└── DEVELOPMENT.md      ← developer/editable-install docs
```
