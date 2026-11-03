#!/usr/bin/env python3
"""Run the manager UI on Linux with a temporary demo configuration."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bluestacks_manager.app import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(["--demo", "--serve", "--host", "0.0.0.0"]))
