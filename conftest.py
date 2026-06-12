"""
Root conftest.py — makes the repo root importable from any working directory.

pytest discovers this file when run from any subdirectory because it walks up
the directory tree looking for conftest.py.  Inserting the repo root at the
front of sys.path lets `import cisd_analysis` and `import scripts.*` work
whether pytest is invoked from the repo root, from `tests/`, or from CI.
"""

import sys
from pathlib import Path

# Repo root is the directory that contains this conftest.py.
_REPO_ROOT = str(Path(__file__).parent.resolve())

if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
