# ADR 0003: Tolerant Scorers, Pass Bands, and Judge Calibration

## Status
Accepted

## Context
Exact string matching fails on natural language generation because semantically identical outputs can differ in phrasing, punctuation, and ordering. Relying on an uncalibrated LLM-as-a-judge introduces position bias (preferring candidate 1), verbosity bias (preferring longer answers), and self-preference.

## Decision
1. Restrict exact match strictly to normalized structured outputs (IDs, category codes, canonical JSON).
2. For natural language outputs, combine multi-criterion rubrics, token F1 overlap, character n-gram similarity, required factual assertions, and forbidden claim detection.
3. Classify all evaluation results into explicit quality bands: `pass` (>=0.75), `needs_review` (0.50 - 0.74), and `fail` (<0.50). Require every score to persist an explanatory rationale.
4. Provide `JudgeCalibrator` with order-swapped pairwise testing to detect position bias, verbosity correlation tracking, and human-ground-truth calibration reporting against `fixtures/calibration_labels.json`.

## Consequences
- **Positive**: Realistic evaluation of generative models that tolerates valid paraphrasing while strictly failing hallucinations and safety violations. Explanations make scores inspectable by screeners.
- **Negative**: Multi-criterion rubrics are slightly more computationally intensive than naive string matching.
