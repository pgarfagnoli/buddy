---
name: migrate
description: Clean up pre-v0.4.0 buddy artifacts left behind by the Homebrew install (legacy hooks in settings.json, old statusLine, user-scope MCP registration, /buddy* command files). Invoke on /buddy:migrate or when the SessionStart nudge suggests it.
---

# Migrate from v0.3.x

Before running, confirm with the user that you can modify `~/.claude/settings.json` and `~/.claude/commands/`. The migration will:

1. Back up `~/.claude/settings.json` with a timestamped `.bak.<epoch>.pre-v0.4.0-migrate` suffix.
2. Strip hook entries whose command contains `buddy.hooks.` or `mcp_creature_bot.hooks.`.
3. Strip the statusLine if its command contains `buddy.scripts.statusline` or `mcp_creature_bot.scripts.statusline`.
4. Run `claude mcp remove --scope user buddy` (and `mcp-creature-bot`) if a user-scope MCP registration with a buddy-flavored command is present.
5. Delete shipped `/buddy*` command files in `~/.claude/commands/` that still match their original marker lines. User-edited ones are left alone.
6. Write a marker in `$CLAUDE_PLUGIN_DATA` so subsequent invocations are no-ops.

**First call: do a dry run.** Call `run_migration` with `dry_run=true` and show the user the report — exactly which entries would be removed, which files would be deleted. If the user approves, call `run_migration` again with `dry_run=false` (the default) to actually apply.

If `status == "nothing-to-do"`, tell the user their install is already clean — no legacy artifacts found.

If `status == "already-migrated"`, tell the user migration already ran; show `marker_contents` for what it did.

After a successful migration, tell the user to reload Claude Code (restart the session) so the stripped hooks stop firing in the current session.
