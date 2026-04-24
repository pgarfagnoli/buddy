---
name: allocate
description: Spend the buddy's unallocated stat points. Invoke on /buddy:allocate or when the user wants to level up stats like "allocate 3 to attack".
---

# Allocate stat points

Parse the user's request into stat→amount pairs. Valid stats are `hp`, `atk`, `def`, `spd`, `luck`, `int`, `res`. Rewrite `def` → `def_` and `int` → `int_` because those are Python reserved word shadows. All values must be non-negative; the total must not exceed the buddy's `stat_points_unspent`.

If no allocation was provided, call `get_buddy` first and report the unspent-points count + current stats, then ask how the user wants to spend them.

Once you have the allocation, call `allocate_stats` with named keyword args. Relay the `display` field.
