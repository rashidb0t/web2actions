"""Entry point so `python -m cli` and `python cli/__main__.py` both work."""

import sys

from cli.main import main

if __name__ == "__main__":
    sys.exit(main())