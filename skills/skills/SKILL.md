---
name: skills
description: Show the buddy's learned skills and equip an active-skill loadout (max 4). Invoke on /buddy:skills or when the user asks about their buddy's skills.
---

# Skills

Call `list_skills` to see what the buddy knows (`known`) and what's currently equipped (`active`). Each skill has `id`, `name`, `description`, `mana_cost`, `trigger`, `effect`, `magnitude`. The server's `slot_cap` field (default 4) is the max size of the active loadout.

Report the known skills and highlight which are active.

If the user wants to change their loadout, gather the chosen skill ids (must be a subset of `known`, no duplicates, ≤ `slot_cap`) and call `set_active_skills` with `skill_ids`. Relay the `display` field.
