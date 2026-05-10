#!/usr/bin/env python3
"""OPP CLI Entry Point - Wrapper for src/opp/cli.py"""

from opp.cli import main

if __name__ == "__main__":
    import sys
    sys.exit(main())
