# EvalForge Architecture Specification

EvalForge is a provider-agnostic evaluation harness engineered for benchmarking prompts, configurations, and models across quality, latency, token consumption, and cost.

## High-Level Architecture

```mermaid
flowchart TD
    subgraph Input ["Specification & Datasets"]
        Spec["experiment.yaml<br/>(Configs, Cases, Scorers, Caps)"]
        Dataset["Dataset (.jsonl)<br/>(Cases, Expected Criteria, Tags)"]
        Prompts["Prompt Templates (.txt)<br/>(Jinja2 / Parameterized)"]
    end

    subgraph Core ["Execution & Storage Engine"]
        Planner["Planner<br/>(Spec Validator & Hasher)"]
        Executor["Executor Engine<br/>(Bounded Concurrency & Retries)"]
        Cost["Cost Tracker<br/>(Preflight Estimate & Spending Cap)"]
        Queue["AsyncWriterQueue<br/>(Serialized SQLite Writer)"]
        DB[("SQLite WAL Store<br/>(Runs, Case Results, Scores, Cache)")]
    end

    subgraph Providers ["Provider Abstraction"]
        Fixture["FixtureAdapter<br/>(Recorded Offline Replay)"]
        Mock["MockAdapter<br/>(Deterministic Simulation)"]
        Hosted["OpenAI/Hosted Adapter<br/>(API, Cache, Retries)"]
    end

    subgraph Scorers ["Evaluation & Calibration"]
        Exact["ExactMatchScorer<br/>(Structured Canonical JSON)"]
        Contains["ContainsScorer<br/>(Required Facts & Forbidden Claims)"]
        Schema["JsonSchemaScorer<br/>(JSON Schema Validation)"]
        Semantic["SemanticSimilarityScorer<br/>(Tolerant Token F1 & N-Gram)"]
        Citation["CitationScorer<br/>(Document Chunk Attributions)"]
        Rubric["RubricJudgeScorer<br/>(Multi-Criterion Explanations & Bands)"]
        Calib["JudgeCalibrator<br/>(Position Swap, Verbosity Bias, Labels)"]
    end

    subgraph Outputs ["Analysis & Portfolio Delivery"]
        CLI["Typer CLI<br/>(validate, run, resume, compare, export)"]
        Gate["CI Regression Gate<br/>(Non-zero exit on threshold breach)"]
        Report["Standalone HTML Report<br/>(Recruiter-Ready KPI Drill-Down)"]
        Server["FastAPI Service<br/>(POST /api/demo/reset, Health, Reports)"]
    end

    Spec --> Planner
    Dataset --> Planner
    Prompts --> Planner
    Planner --> Cost
    Planner --> Executor
    Cost --> Executor
    Executor --> Fixture
    Executor --> Mock
    Executor --> Hosted
    Executor --> Queue
    Queue --> DB

    DB --> Scorers
    Scorers --> Queue
    DB --> CLI
    DB --> Gate
    DB --> Report
    DB --> Server
```

## Key Architectural Principles

1. **Deterministic Offline CI Gate**:
   Pull request CI operates 100% offline using recorded fixtures (`fixtures/recorded_responses.json`). No network calls are made during CI, eliminating flakes and budget consumption.
2. **SQLite WAL with Serialized Writer Queue**:
   Parallel async worker tasks generate model outputs concurrently without database locking because all SQLite writes are serialized through an `asyncio.Queue` worker.
3. **No Exact Matching on Generative Text**:
   Exact matching is restricted to canonical structured outputs. Free-form text uses multi-criterion rubrics, semantic overlap, required fact verification, and forbidden claim detection.
4. **Transparent Cost Controls**:
   Preflight estimation alerts developers before execution, and runtime spending caps halt evaluation cleanly before budget overruns occur.
5. **Calibrated Judges**:
   Judges are calibrated for position bias (order-swapped comparisons), verbosity bias, and agreement against human ground truth labels.
