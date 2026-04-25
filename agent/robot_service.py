#!/usr/bin/env python

from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    from service.main import main
except ImportError:
    from agent.service.main import main


if __name__ == "__main__":
    main()
