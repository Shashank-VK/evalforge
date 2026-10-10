from abc import ABC, abstractmethod
from evalforge.models import DatasetCase, CaseResult, Score
from evalforge.constants import SCORER_VERSION

class BaseScorer(ABC):
    """Abstract base class for all evaluation scorers."""
    name: str = "base"
    version: str = SCORER_VERSION

    @abstractmethod
    def score_case(self, case: DatasetCase, result: CaseResult) -> Score:
        """Scores a single case result and returns a Score instance with explanation and pass band."""
        pass
