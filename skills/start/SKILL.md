---
name: start
description: Pick and name a starter buddy. Invoke when the user wants to begin, start a new buddy, or says things like "I want to pick a starter".
---

# Start a new buddy

First call `list_species` to roll 3 random starter candidates on the `buddy` MCP server. Present the three options to the user (id, display_name, kind, blurb, base stats). Ask which one they'd like and what name to give it.

Once they pick: call `choose_buddy` with `species_id` and `name` (1–20 non-whitespace chars). Relay the resulting `display` field.

If `get_buddy` already shows an existing buddy, don't overwrite. Tell the user they already have one (give the name + species) and suggest `/buddy:rename` or — only if they confirm they want to start over — `reset_buddy` with `confirm=true`.
