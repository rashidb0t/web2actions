"""Entry point so `python -m cli`, `python cli/__main__.py`, and the installed
`web2actions` command all work.
"""

import os
import sys

# Ensure the repo root is importable so `cli.main` resolves regardless of how
# this file is invoked.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from cli.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())