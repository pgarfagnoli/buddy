# homebrew-buddy

A Homebrew tap hosting [`mcp-creature-bot`](./mcp-creature-bot/) — an RPG buddy for Claude Code. Pokemon-style ASCII creature in a tmux sidecar pane that gains XP every time you submit a prompt.

## Install

```bash
brew tap pgarfagnoli/buddy
brew install mcp-creature-bot
mcp-creature-bot-install
```

`brew install` puts the Python package and its CLI entry points into a Homebrew-managed virtualenv. `mcp-creature-bot-install` wires everything up at user scope: registers the MCP server, drops `/buddy*` slash commands into `~/.claude/commands/`, merges hooks into `~/.claude/settings.json`, and installs the buddy statusLine.

See [`mcp-creature-bot/README.md`](./mcp-creature-bot/README.md) for the full feature list, usage, and architecture notes.

## Uninstall

```bash
mcp-creature-bot-uninstall
brew uninstall mcp-creature-bot
brew untap pgarfagnoli/buddy
```

## Repository layout

```
homebrew-buddy/
├── Formula/
│   └── mcp-creature-bot.rb    ← Homebrew formula
└── mcp-creature-bot/           ← Python package source
    ├── pyproject.toml
    ├── src/mcp_creature_bot/
    └── README.md
```

Working on the source directly? See `mcp-creature-bot/README.md` for the editable-install flow.
