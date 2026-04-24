---
name: migrate
description: One-shot cleanup of pre-v0.4.0 buddy artifacts — legacy hooks/statusLine/MCP registration/command files in ~/.claude/, plus (optionally) the old Homebrew package and tap. Invoke on /buddy:migrate, when the SessionStart nudge suggests it, or when the user asks Claude to clean up their old buddy install.
---

# Migrate from v0.3.x

Perform the upgrade in two phases.

## Phase 1 — clean ~/.claude/ state via the `run_migration` MCP tool

Always do a **dry run first**. Call `run_migration` with `dry_run=true` on the `buddy` MCP server. The response is a report describing every change that would happen:

- `legacy_hooks`: hook entries in `~/.claude/settings.json` whose command contains `buddy.hooks.` or `mcp_creature_bot.hooks.`.
- `legacy_statusline`: a statusLine command pointing at `buddy.scripts.statusline` (null if absent).
- `legacy_mcp_servers`: user-scope MCP registrations named `buddy` or `mcp-creature-bot`.
- `legacy_commands`: `/buddy*` files in `~/.claude/commands/` whose content still matches the shipped markers (user-edited ones are left alone).

Show the user the dry-run report. If there's nothing to do (`status == "nothing-to-do"` or `already-migrated`), tell them their install is clean and skip to Phase 2.

Otherwise, confirm with the user and call `run_migration` again (with `dry_run=false` or no arg). The tool backs up `settings.json` with a timestamped `.bak.<epoch>.pre-v0.4.0-migrate` suffix before any mutation. Relay the report, especially the `settings_backup` path so the user knows where the backup is.

## Phase 2 — uninstall the old Homebrew package if present

Check whether `brew` still has the legacy buddy install. Run these shell checks with the Bash tool and tell the user what you find:

```bash
brew list buddy 2>/dev/null && echo "pkg present" || echo "pkg absent"
brew tap | grep -E "pgarfagnoli/(homebrew-)?buddy" || echo "tap absent"
```

If either is present, ask the user if they want to clean it up. On confirmation, run these via the Bash tool:

```bash
brew uninstall buddy                     # only if pkg present
brew untap pgarfagnoli/buddy             # only if that tap is present
brew untap pgarfagnoli/homebrew-buddy    # only if the older tap name is present
```

Each command is prefixed `brew …`, so ask the user to approve each Bash call as it comes up (or pre-approve the pattern in their permissions if they want).

If neither is present, skip this phase and report "Homebrew is already clean."

## Wrap-up

After both phases, tell the user to **restart Claude Code** so the stripped hooks stop firing in the currently open session. Mention that their buddy's state survived — the creature at `~/.claude/plugins/data/buddy/state.json` was untouched, and a pre-migration snapshot still sits at `~/.claude/buddy/` as a backup (which the plugin's `paths.py` will re-copy from if the plugin data dir is ever wiped).
