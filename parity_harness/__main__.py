"""Module entry point so the harness can be run as ``python -m``.

Delegates to :func:`parity_harness.harness.main`.
"""

from __future__ import annotations

import sys

from .harness import main

if __name__ == "__main__":
    sys.exit(main())
