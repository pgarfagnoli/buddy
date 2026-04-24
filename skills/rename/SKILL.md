---
name: rename
description: Rename the buddy. Invoke on /buddy:rename or when the user wants to change their buddy's name.
---

# Rename buddy

Call `rename_buddy` with the new `name` (1–20 non-whitespace chars). If the user didn't supply a name, ask first. Relay the resulting `display` field.
