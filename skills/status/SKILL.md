---
name: status
description: Show the user's RPG buddy status — level, HP/MP, XP, stats, active quest, recent events. Invoke when the user asks how their buddy is doing, says things like "how's my buddy", or types /buddy:status.
---

# Buddy status

Call the `get_buddy` tool on the `buddy` MCP server.

If the returned payload has `buddy: null`, prompt the user to pick a starter by calling the `list_species` tool and asking them to choose one (then they can use `/buddy:start` to commit).

Otherwise, relay the `display` field verbatim — it already contains a formatted HP/MP/XP line, stat block, active skills, recent events, and evolution/mythic readiness hints. Don't re-format or summarize; the server pre-rendered it for fast relay.
