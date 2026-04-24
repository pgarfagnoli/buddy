---
name: quest
description: Send the buddy on a quest, or list available quest zones. Invoke on /buddy:quest or when the user says things like "send my buddy on a quest" or "list quest zones".
---

# Quest

If the user specified a zone id (e.g. `/buddy:quest forest`): call `start_quest` with `zone_id`. Relay the `display` field — the server formats the rolled quest name and estimated success probability.

Otherwise: call `list_zones` first. Present the zones with `id`, `name`, `recommended_level`, `blurb`, `difficulty_range`, `xp_range`, and `duration_range_human`. Ask the user which zone to send the buddy to. Then call `start_quest` with the chosen `zone_id`.

If `get_buddy` shows `buddy: null`, tell the user to `/buddy:start` first.
