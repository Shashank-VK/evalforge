# Scorer Catalogue & Honest Limitations

Every evaluation metric has trade-offs and failure modes. Below is the honest taxonomy of scorers implemented in EvalForge:

| Scorer | Intended Use Case | Core Strength | Known Limitation & Mitigation |
| :--- | :--- | :--- | :--- |
| **Exact Match** | Canonical IDs, status codes, structured category outputs. | Deterministic, zero false positives for normalized strings. | **Failure mode:** Fails valid natural language paraphrases. *Mitigation:* Restrict strictly to structured enum and schema tests. |
| **Contains / Required Facts** | Verifying essential factual terms (e.g. "14 days", "99.95% SLA"). | Fast, explainable, highlights missing factual keywords. | **Failure mode:** Vulnerable to keyword stuffing without conceptual coherence. *Mitigation:* Paired with forbidden claim detection and semantic similarity. |
| **Forbidden Claims** | Detecting safety violations, non-disclosure breaches, hallucinations. | Immediate zero-score failure on dangerous content. | **Failure mode:** Lexical substring matching can flag negation (e.g. "we do not guarantee 100%"). *Mitigation:* Phrase boundaries and context parsing. |
| **JSON Schema** | Structured tool call payloads, programmatic responses. | Verifies types, required keys, and formatting with JSON Schema. | **Failure mode:** Valid syntax does not guarantee truthful content. *Mitigation:* Evaluated alongside semantic and rubric scorers. |
| **Semantic Similarity** | Tolerant generative text comparison (token F1 + 3-gram). | Accommodates synonyms, word order swaps, and natural phrasing. | **Failure mode:** Can reward vague or evasive text with high overlap. *Mitigation:* Evaluated in tandem with factual criteria. |
| **Citation Scorer** | Grounded question-answering across knowledge chunks. | Verifies presence and precision of source markers (`[doc#chunk]`). | **Failure mode:** Does not verify that the chunk actually supports the claim on its own. *Mitigation:* Cross-referenced with RAG faithfulness checks. |
| **Rubric Judge** | Multi-criterion quality assessment (completeness, factuality, tone). | Nuanced, provides granular sub-scores and human-readable explanations. | **Failure mode:** Sensitive to prompt framing, length bias, and position bias. *Mitigation:* Calibrated using order-swapping and human calibration datasets. |

## Judge Bias Mitigation Framework

1. **Position Bias:**
   In pairwise comparisons, candidates presented first often receive higher preference. EvalForge's `JudgeCalibrator` executes order-swapped runs `(A, B)` and `(B, A)` and reports the consistency rate.
2. **Verbosity Bias:**
   Longer outputs frequently score higher regardless of substance. EvalForge computes Pearson correlation between token length and judge score to detect length exploitation.
3. **Self-Preference Bias:**
   Models evaluated by the same family often rate themselves higher. EvalForge isolates prompt configurations, records hashes, and calibrates against external human labels.
