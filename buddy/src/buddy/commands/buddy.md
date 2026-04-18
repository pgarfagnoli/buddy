---
description: Interact with your RPG buddy (status, start/stop/refresh sidebar, allocate stats, quest, claim, evolve, rename, uninstall).
argument-hint: [start|stop|refresh|allocate|quest|claim|evolve|rename|uninstall] [args…]
allowed-tools: Bash(python3 -m buddy.scripts.uninstall:*)
---

Parse `$ARGUMENTS`. First token = subcommand. All MCP tools are on the `buddy` server. Most responses include a `display` field — relay it directly as your answer.

### (empty) / `status`
Call `start_pane` (ignore result), then `get_buddy`. Relay `display`. If `buddy` is null, call `list_species` and ask user to pick.

### `start` / `stop` / `refresh`
`start`: call `start_pane`. `stop`: call `stop_pane`. `refresh`: call `refresh_pane`. Relay `display`.

### `allocate <stat> <amount> [...]`
Parse stat/amount pairs. `def` → `def_`, `int` → `int_`. Call `allocate_stats`. If no args, call `get_buddy` first to show unspent points.

### `quest [zone_id]`
With zone: call `start_quest`. Without: call `list_zones`, show zones, ask user to pick. Relay `display`.

### `claim`
Call `claim_quest`. On error (not finished), call `check_quest` and report time left. Relay `display`.

### `evolve [species_id]`
With id: call `commit_evolution`. Without: call `get_buddy`, check `evolution_ready` block. If `at_or_past_level` + `any_eligible`: list branches with ✓/✗ checks, ask user to pick. If not at level: report current level vs trigger. If mythic_ready: invent a mythic name (1-32 chars), blurb (1-200 chars), stat_bonus (sum ≤ cap_total, each ≤ cap_per_stat), call `commit_legendary_evolution`.

### `rename <name>`
Call `rename_buddy`. If no name given, ask.

### `uninstall`
Run `python3 -m buddy.scripts.uninstall`.
