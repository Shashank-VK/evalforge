import json
import uuid
from typing import Any
import jsonschema
from evalforge.scorers.base import BaseScorer
from evalforge.models import DatasetCase, CaseResult, Score
from evalforge.constants import PASS_BAND_PASS, PASS_BAND_FAIL

class JsonSchemaScorer(BaseScorer):
    """Scorer that validates structured model outputs against a JSON Schema."""
    name = "json_schema"

    def score_case(self, case: DatasetCase, result: CaseResult) -> Score:
        score_id = str(uuid.uuid4())
        expected_dict = case.expected or {}
        schema = expected_dict.get("json_schema")

        if not schema:
            return Score(
                id=score_id,
                run_id=result.run_id,
                case_id=case.id,
                config_id=result.config_id,
                scorer_name=self.name,
                score=1.0,
                passed=True,
                band=PASS_BAND_PASS,
                explanation="No json_schema specified in case; check skipped.",
                details={"skipped": True}
            )

        # Parse model response as JSON
        try:
            parsed_data = json.loads(result.response_text.strip())
        except Exception as e:
            return Score(
                id=score_id,
                run_id=result.run_id,
                case_id=case.id,
                config_id=result.config_id,
                scorer_name=self.name,
                score=0.0,
                passed=False,
                band=PASS_BAND_FAIL,
                explanation=f"Response is not valid JSON: {str(e)}",
                details={"json_error": str(e), "raw_text": result.response_text[:200]}
            )

        # Validate schema
        if isinstance(schema, str):
            # If schema name is provided as placeholder or string
            schema_obj = {"type": "object"}
        else:
            schema_obj = schema

        try:
            jsonschema.validate(instance=parsed_data, schema=schema_obj)
            return Score(
                id=score_id,
                run_id=result.run_id,
                case_id=case.id,
                config_id=result.config_id,
                scorer_name=self.name,
                score=1.0,
                passed=True,
                band=PASS_BAND_PASS,
                explanation="Model output successfully conforms to the required JSON schema.",
                details={"valid": True}
            )
        except jsonschema.ValidationError as ve:
            return Score(
                id=score_id,
                run_id=result.run_id,
                case_id=case.id,
                config_id=result.config_id,
                scorer_name=self.name,
                score=0.0,
                passed=False,
                band=PASS_BAND_FAIL,
                explanation=f"JSON schema validation failed: {ve.message}",
                details={"validation_error": ve.message, "path": list(ve.path)}
            )
