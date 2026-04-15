# homebrew-buddy

A Homebrew tap hosting [`buddy`](./buddy/) — an RPG buddy for Claude Code. Pokemon-style ASCII creature in a tmux sidecar pane that gains XP every time you submit a prompt.

## Install

```bash
brew tap pgarfagnoli/buddy
brew install buddy
buddy-install
```

`brew install buddy` puts the Python package and its CLI entry points into a Homebrew-managed virtualenv, and pulls in `tmux` automatically if it isn't already installed. `buddy-install` then wires everything up at user scope: registers the MCP server, drops `/buddy*` slash commands into `~/.claude/commands/`, merges hooks into `~/.claude/settings.json`, and installs the buddy statusLine.

See [`buddy/README.md`](./buddy/README.md) for the full feature list, usage, and architecture notes.

## Uninstall

```bash
buddy-uninstall
brew uninstall buddy
brew untap pgarfagnoli/buddy
```

## Repository layout

```
homebrew-buddy/
├── Formula/
│   └── buddy.rb    ← Homebrew formula (installs as `brew install buddy`)
└── buddy/          ← Python package source
    ├── pyproject.toml
    ├── src/buddy/
    └── README.md
```

Working on the source directly? See `buddy/README.md` for the editable-install flow.
