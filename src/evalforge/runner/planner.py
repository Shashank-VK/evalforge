import hashlib
import json
import os
from pathlib import Path
from typing import Any
import yaml
from jinja2 import Template
from evalforge.models import Dataset, DatasetCase, ModelConfig, ExperimentSpec
from evalforge.exceptions import ValidationFailedError
from evalforge.logger import get_logger

logger = get_logger(__name__)

class Planner:
    """Loads, validates, and prepares experiments for execution."""

    @staticmethod
    def load_dataset(dataset_path: str) -> Dataset:
        """Loads and validates a JSONL dataset."""
        if not os.path.exists(dataset_path):
            raise ValidationFailedError(f"Dataset file not found at: {dataset_path}")

        cases: list[DatasetCase] = []
        seen_ids = set()
        raw_lines = []

        with open(dataset_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                clean_line = line.strip()
                if not clean_line or clean_line.startswith("#"):
                    continue
                try:
                    obj = json.loads(clean_line)
                except json.JSONDecodeError as e:
                    raise ValidationFailedError(f"Line {line_no} in {dataset_path} is invalid JSON: {e}")

                if "id" not in obj:
                    raise ValidationFailedError(f"Line {line_no} in {dataset_path} is missing required 'id' field")
                if "input" not in obj or not isinstance(obj["input"], dict):
                    raise ValidationFailedError(f"Case '{obj.get('id')}' in {dataset_path} must have a valid 'input' dict")

                if obj["id"] in seen_ids:
                    raise ValidationFailedError(f"Duplicate case id '{obj['id']}' found in {dataset_path}")

                seen_ids.add(obj["id"])
                case = DatasetCase(**obj)
                cases.append(case)
                raw_lines.append(clean_line)

        if not cases:
            raise ValidationFailedError(f"Dataset {dataset_path} contains no valid cases")

        content_hash = hashlib.sha256("".join(raw_lines).encode("utf-8")).hexdigest()[:16]
        dataset_name = Path(dataset_path).stem
        return Dataset(name=dataset_name, content_hash=content_hash, cases=cases)

    @staticmethod
    def load_experiment_spec(spec_path: str) -> ExperimentSpec:
        """Loads and validates an experiment YAML specification."""
        if not os.path.exists(spec_path):
            raise ValidationFailedError(f"Experiment spec file not found at: {spec_path}")

        with open(spec_path, "r", encoding="utf-8") as f:
            try:
                data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise ValidationFailedError(f"Invalid YAML in {spec_path}: {e}")

        if not isinstance(data, dict):
            raise ValidationFailedError(f"Experiment specification in {spec_path} must be a dictionary")

        try:
            spec = ExperimentSpec(**data)
        except Exception as e:
            raise ValidationFailedError(f"Specification validation error: {e}")

        # Resolve prompt contents and compute config hashes
        base_dir = Path(spec_path).parent
        for config in spec.configs:
            prompt_content = Planner.resolve_prompt_content(config.prompt, base_dir)
            config.config_hash = config.compute_hash(prompt_content)

        spec.spec_hash = spec.compute_hash()
        return spec

    @staticmethod
    def resolve_file_path(path_str: str, base_dir: Path) -> Path:
        """Resolves a file path trying base_dir, current working directory, and parent directories."""
        p = Path(path_str)
        if p.is_absolute() and p.exists():
            return p
        candidates = [
            base_dir / p,
            Path.cwd() / p,
            base_dir.parent / p,
            Path(__file__).resolve().parent.parent.parent.parent / p
        ]
        for c in candidates:
            if c.exists():
                return c.resolve()
        return base_dir / p

    @staticmethod
    def resolve_prompt_content(prompt_field: str, base_dir: Path) -> str:
        """Resolves prompt field whether it is an inline template or a file path."""
        resolved = Planner.resolve_file_path(prompt_field, base_dir)
        if resolved.is_file():
            try:
                return resolved.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning("Could not read prompt file %s: %s", resolved, e)
        # Inline template
        return prompt_field

    @staticmethod
    def render_prompt(prompt_template: str, input_vars: dict[str, Any]) -> str:
        """Renders prompt using Jinja2 or python string formatting."""
        try:
            t = Template(prompt_template)
            return t.render(**input_vars)
        except Exception:
            try:
                return prompt_template.format(**input_vars)
            except Exception:
                # If rendering fails, return raw template with variable summary
                return prompt_template
