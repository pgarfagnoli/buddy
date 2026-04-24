---
name: claim
description: Claim rewards from a completed buddy quest. Invoke on /buddy:claim or when the user says their quest is done.
---

# Claim quest rewards

Call `claim_quest` on the `buddy` MCP server. Relay the `display` field — it summarizes success/failure, XP gained, items looted, HP damage, and any skills that fired during combat.

If the call errors with "quest not finished" or similar, call `check_quest` and report how much time is left. If no quest is active, tell the user to `/buddy:quest`.
