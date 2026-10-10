import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from evalforge.models import ExperimentSpec
from evalforge.storage.repository import Repository
from evalforge.runner.planner import Planner
from evalforge.runner.executor import Executor
from evalforge.scorers.registry import ScorerRegistry
from evalforge.config import get_settings
from evalforge.logger import get_logger

logger = get_logger(__name__)

from evalforge.seed import seed_demo_data

if __name__ == "__main__":
    settings = get_settings()
    repo = Repository(settings.db_path)
    seeded = seed_demo_data(repo)
    print(f"Seeded runs successfully: {seeded}")
