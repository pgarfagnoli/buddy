---
name: pane
description: Open the buddy-pane viewer in a new terminal window. Invoke on /buddy:pane or when the user asks to "open the buddy window", "show the buddy pane", "watch my buddy", etc.
---

# Open buddy-pane

Launch the animated buddy-pane viewer in a new terminal window so the user can watch their buddy while they work.

## Steps

1. Determine the path to buddy-pane. Check in order:
   - `~/.local/bin/buddy-pane` (symlinked on session start)
   - `$CLAUDE_PLUGIN_ROOT/bin/buddy-pane` if the env var is set
   - The repo-local `bin/buddy-pane` relative to this plugin

2. Verify the resolved path exists. If not, tell the user buddy-pane wasn't found and suggest reinstalling the plugin.

3. Open a **new terminal window** by running this bash command (macOS):

```bash
osascript -e "tell application \"Terminal\"
    activate
    do script \"exec <BUDDY_PANE_PATH>\"
end tell"
```

Replace `<BUDDY_PANE_PATH>` with the resolved absolute path from step 1.

4. Tell the user the buddy-pane window is open. Mention they can close it with Ctrl-C or by closing the terminal window.

## Notes

- Do NOT run buddy-pane in the current Claude Code session — it takes over the terminal with a render loop. Always open a new window.
- The pane auto-discovers the buddy state file; no env vars need to be passed.
- If the user is on Linux (not macOS), suggest they open a second terminal manually and run `buddy-pane` or the full path.
