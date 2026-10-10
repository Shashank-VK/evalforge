"""EvalForge: Provider-agnostic LLM evaluation harness."""

__version__ = "0.1.0"
__author__ = "Shashank Karamudi"

from evalforge.models import (
    Dataset,
    DatasetCase,
    ModelConfig,
    ExperimentSpec,
    CaseResult,
    Score,
    Run,
    ComparisonResult
)
from evalforge.storage.repository import Repository
from evalforge.runner.planner import Planner
from evalforge.runner.executor import Executor
from evalforge.scorers.registry import ScorerRegistry

__all__ = [
    "Dataset",
    "DatasetCase",
    "ModelConfig",
    "ExperimentSpec",
    "CaseResult",
    "Score",
    "Run",
    "ComparisonResult",
    "Repository",
    "Planner",
    "Executor",
    "ScorerRegistry"
]
