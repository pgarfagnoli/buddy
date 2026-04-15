---
description: Interact with your RPG buddy (status, start/stop/refresh sidebar, allocate stats, quest, claim, rename, uninstall).
argument-hint: [start|stop|refresh|allocate|quest|claim|rename|uninstall] [args…]
allowed-tools: Bash(python3 -m mcp_creature_bot.scripts.uninstall:*)
---

Parse `$ARGUMENTS`. The first token is the subcommand; anything after it is subcommand args. Treat empty arguments and `status` as the same thing. All MCP tools below live on the `mcp-creature-bot` server.

### (empty) or `status`

1. Call `start_pane`. Ignore the result — `spawned` and `already_live` are both fine, and a tmux error just means we can't auto-spawn (keep going, don't block on it).
2. Call `get_buddy` and present the result compactly: name, species, level, HP/max_hp, XP/xp_to_next, unspent stat points, and the active quest (if any) with time remaining. Mention anything in `recent_events` (level-ups, quest completions). If the response has a `mythic` block, use that `display_name` and `blurb` as the buddy's identity (the overlay supersedes the species's own name).
3. If the response includes an `evolution_preview` block, mention it: name the `predicted_form`, note the `trigger_level`, and explain that the buddy's `dominant_stat` is steering the branch. Nudge the user toward a different allocation if they want a different form.
4. If the response includes a `mythic_ready` block, the buddy has reached the threshold of a unique **mythic evolution**. Tell the player their buddy is on the verge of becoming a legend — quote the `apex_form` and `trigger_level` — and ask if they want to invoke the mythic evolution now. If they agree, INVENT a fantastical name and commit it:
   - `display_name`: 1–32 chars, evocative and mythic (not a real animal — this is the fantastical tier). Draw inspiration from `apex_form`, the buddy's name, and `recent_events` history.
   - `blurb`: 1–200 chars, short flavor sentence describing the transformation.
   - `stat_bonus`: dict using keys from `{hp, atk, def_, spd, luck, int_, res}` (note the trailing underscores on `def_` and `int_`). Sum ≤ `cap_total` (40). No single stat > `cap_per_stat` (15). All values non-negative ints. Lean into `current_stats` — pick a distribution that amplifies the buddy's strengths or shores up a weakness; make it feel intentional for this specific buddy.
   - Then call `commit_legendary_evolution(display_name, blurb, stat_bonus)`.
   On success, tell the player the new name, blurb, and the updated stats.
5. If `buddy` is null, tell the user they don't have a buddy yet, call `list_species` so they can pick a starter, then call `choose_buddy` with their chosen species_id and name.

### `start`

Call `start_pane`.

- `status: "spawned"` → one short sentence confirming the buddy is now visible in the right-hand tmux pane.
- `status: "already_live"` → tell the user the pane is already running.
- Tmux error → tell the user to launch Claude Code inside a tmux session (`tmux new -s dev` then `claude`) and retry.

### `stop`

Call `stop_pane`.

- `status: "stopped"` → confirm the pane has been closed.
- `status: "no_pane"` → tell the user there was no pane to stop.

### `refresh`

Call `stop_pane`, then call `start_pane`. Tell the user the sidebar pane was refreshed. If `stop_pane` returned `no_pane`, that's fine — just report that it was started.

### `allocate <stat> <amount> [<stat> <amount> ...]`

Parse the remaining args as stat/amount pairs (valid stats: `hp`, `atk`, `def`, `spd`, `luck`, `int`, `res`). Then call `allocate_stats`. **Important**: `def` must be passed as `def_` and `int` must be passed as `int_` (Python naming — the trailing underscore avoids the reserved word / builtin).

Example: `/buddy allocate atk 2 def 1 int 1` → call `allocate_stats` with `{"atk": 2, "def_": 1, "int_": 1}`.

If no args were given after the subcommand, call `get_buddy` first, tell them how many points are unspent, and ask how they want to distribute them. After the call, show the updated stats and how many points remain.

### `quest [zone_id]`

If a zone id is present (e.g. `meadow`, `forest`, `cave`, `ruins`, `peaks`), call `start_quest` with that zone id — the server will smart-pick a quest from the zone based on the buddy's stat profile. Otherwise call `list_zones` and show the user each zone's name, recommended level, blurb, difficulty range, XP range, duration range, and which stats are useful there. Ask them to pick a zone.

After starting, tell the user which specific quest the buddy rolled (from `rolled_quest_name`), roughly how confident the buddy feels (from `estimated_success`, e.g. "Atlas felt about 65% confident about Mushroom Forage"), how long it'll take, and remind them to run `/buddy claim` when it's ready.

### `claim`

Call `claim_quest`. If it errors because the quest isn't finished yet, call `check_quest` instead and tell the user how much time is left.

On success, show the user the quest result (success/failure), XP gained, any items found, HP damage if applicable, and any level-ups from `recent_events`.

### `rename <new name>`

Call `rename_buddy` with `name=` the trimmed remaining args. If no name was given, ask the user what name they want.

### `uninstall`

Run:

```bash
python3 -m mcp_creature_bot.scripts.uninstall
```

Then explain to the user what it did: removed the user-scope MCP server registration, deleted the bundled `/buddy` command from `~/.claude/commands/`, reverted the statusLine, deleted state under `~/.claude/mcp-creature-bot/`, and killed any running sidecar panes. The Python package itself is still installed — they can `pip uninstall mcp-creature-bot` to remove it entirely.
