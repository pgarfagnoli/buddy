---
name: evolve
description: Evolve the buddy into a new form, or commit a mythic (legendary) post-apex evolution. Invoke on /buddy:evolve or when the user talks about evolving their buddy.
---

# Evolve

Call `get_buddy` first. Look at the response:

- **If `evolution_ready` is present**: that means the buddy is at or past its species' `evolves_at` level.
  - If `at_or_past_level` is true and `any_eligible` is true, list the branches (with display_name + the ✓/✗ stat-requirement checks). Ask the user to pick. Then call `commit_evolution` with `species_id`.
  - If the buddy is below `trigger_level`, tell the user what level they need.

- **If `mythic_ready` is present**: the buddy has reached its apex form's `mythic_at` level and is eligible for a unique legendary evolution. Invent:
  - `display_name` (1–32 chars) — a fantastical name appropriate to the apex form + the buddy's story so far.
  - `blurb` (1–200 chars) — a short flavor description.
  - `stat_bonus` — a dict of stat → int bonus. Sum must be ≤ `cap_total` (40). Each value must be ≤ `cap_per_stat` (15). Bias toward the buddy's existing stat strengths. Keys are `hp`, `atk`, `def_`, `spd`, `luck`, `int_`, `res`.

  Show the proposal to the user, get confirmation, then call `commit_legendary_evolution`.

- **If neither is present**: the buddy can't evolve yet. Report their current level and what needs to happen next.

Relay the `display` field from any successful commit.
