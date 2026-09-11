#!/usr/bin/env python3
"""Compatibility entry point for the shared demo runtime helper."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from scripts.demo import demo_runtime as _runtime
except ModuleNotFoundError:  # Support direct invocation outside the repository cwd.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.demo import demo_runtime as _runtime


if __name__ == "__main__":
    raise SystemExit(_runtime.main())

# Existing tests and downstream imports keep receiving the actual helper module,
# so monkeypatching its globals behaves exactly as it did before the refactor.
sys.modules[__name__] = _runtime
