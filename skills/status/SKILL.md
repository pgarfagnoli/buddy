---
name: status
description: Show the user's RPG buddy status — level, HP, XP, stats, active quest, recent events. Invoke when the user asks how their buddy is doing, or types /buddy:status.
---

# Buddy status

Call the `get_buddy` tool on the `buddy` MCP server. It returns a JSON object with the current buddy state.

Walking-skeleton behavior: the stub tool currently returns a placeholder payload like `{"buddy": null, "note": "walking skeleton — real tools pending"}`. Display the returned JSON verbatim so the user can confirm the plugin → MCP → response path works end to end.

Once the real `get_buddy` is ported, this skill will render a sprite, a stat table, an HP/XP bar, and the last few events.
