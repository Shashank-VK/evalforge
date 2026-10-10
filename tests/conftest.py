import os
import tempfile
import pytest
from pathlib import Path
from evalforge.config import Settings, set_settings
from evalforge.storage.repository import Repository
from evalforge.models import DatasetCase, ModelConfig, ExperimentSpec

@pytest.fixture
def temp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)

@pytest.fixture
def repo(temp_db_path):
    r = Repository(temp_db_path)
    yield r

@pytest.fixture
def sample_case():
    return DatasetCase(
        id="test-case-01",
        input={"question": "What is the return policy?", "customer_tier": "gold"},
        expected={
            "contains": ["refund", "14 days"],
            "forbidden": ["never refund"],
            "relevant_chunk_ids": ["doc1#chunk1"],
            "exact_match": "Refund within 14 days"
        },
        tags=["policy", "test"]
    )

@pytest.fixture
def sample_config():
    return ModelConfig(
        id="test-config",
        provider="mock",
        model="deterministic-v1",
        prompt="Question: {{ question }}",
        temperature=0.0,
        max_tokens=150
    )
