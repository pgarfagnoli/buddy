"""SessionEnd hook: currently a no-op.

Wired so the hook config is stable across releases; if we ever want
per-session cleanup, it lives here.
"""
from __future__ import annotations

import sys


def main() -> int:
    return 0


if __name__ == "__main__":
    sys.exit(main())
