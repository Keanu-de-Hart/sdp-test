"""Runtime configuration for the RAT backend."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
DATA_DIR = Path(os.environ.get("RAT_DATA_DIR", BASE_DIR / "data"))
REPOS_DIR = DATA_DIR / "repos"
DB_PATH = DATA_DIR / "rat.db"
FRONTEND_DIST = Path(os.environ.get("RAT_FRONTEND_DIST", BASE_DIR.parent / "frontend" / "dist"))

DATA_DIR.mkdir(parents=True, exist_ok=True)
REPOS_DIR.mkdir(parents=True, exist_ok=True)
