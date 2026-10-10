import os
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from evalforge.config import get_settings
from evalforge.storage.repository import Repository
from evalforge.reporting.html_reporter import HtmlReporter
from evalforge.reporting.json_reporter import JsonReporter
from evalforge.comparison.comparator import RunComparator
from evalforge.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="EvalForge API",
    description="Provider-agnostic LLM evaluation harness and comparison service",
    version="0.1.0"
)

def get_repo() -> Repository:
    settings = get_settings()
    return Repository(settings.db_path)

@app.get("/health")
def health_check():
    settings = get_settings()
    return {
        "status": "healthy",
        "service": "EvalForge",
        "demo_mode": settings.demo_mode
    }

@app.get("/api/runs")
def list_runs():
    repo = get_repo()
    runs = repo.list_runs()
    return {"runs": [r.model_dump() for r in runs]}

@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    repo = get_repo()
    run = repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return {"run": run.model_dump()}

@app.get("/api/runs/{run_id}/results")
def get_run_results(run_id: str):
    repo = get_repo()
    run = repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    results = repo.get_case_results(run_id)
    scores = repo.get_scores(run_id)
    return {
        "run_id": run_id,
        "results": [r.model_dump() for r in results],
        "scores": [s.model_dump() for s in scores]
    }

@app.get("/api/runs/{run_id}/report", response_class=HTMLResponse)
def get_html_report(run_id: str):
    repo = get_repo()
    try:
        html = HtmlReporter.generate_html(run_id, repo)
        return HTMLResponse(content=html)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/api/compare/{baseline_id}/{candidate_id}")
def compare_runs(baseline_id: str, candidate_id: str):
    repo = get_repo()
    try:
        comparison = RunComparator.compare(baseline_id, candidate_id, repo)
        return comparison.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/demo/reset")
def demo_reset(
    x_demo_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    """Guarded, demo-only reset endpoint.
    Restores seed datasets and sample benchmark suites, clears session caches,
    is idempotent, and is strictly disabled outside demo mode.
    """
    settings = get_settings()

    # 1. Guard: DEMO_MODE must be active
    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: /api/demo/reset is disabled outside demo mode (DEMO_MODE=false)"
        )

    # 2. Guard: Authentication check
    provided_key = None
    if x_demo_key:
        provided_key = x_demo_key
    elif authorization and authorization.lower().startswith("bearer "):
        provided_key = authorization.split(" ", 1)[1]

    if not provided_key or provided_key != settings.demo_admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: invalid or missing demo admin key"
        )

    # 3. Action: Clear database and reseed demo runs
    repo = get_repo()
    repo.clear_all()

    # Reseed baseline and candidate runs
    from evalforge.seed import seed_demo_data
    seeded_runs = seed_demo_data(repo)

    logger.info("Demo reset executed successfully. Seeded %d runs.", len(seeded_runs))
    return {
        "status": "reset_successful",
        "message": "EvalForge database and report sessions reseeded successfully",
        "demo_mode": True,
        "runs_seeded": seeded_runs
    }

@app.get("/", response_class=HTMLResponse)
def index_page():
    repo = get_repo()
    runs = repo.list_runs()
    settings = get_settings()

    rows = ""
    for r in runs:
        m = r.aggregate_metrics or {}
        score = f"{m.get('mean_score', 0.0):.4f}"
        rows += f"""
        <tr>
            <td><strong>{r.name}</strong></td>
            <td><code>{r.id[:8]}...</code></td>
            <td><span class="badge badge-success">{r.status}</span></td>
            <td>{score}</td>
            <td>{r.completed_cases}/{r.total_cases}</td>
            <td>${r.total_cost_usd:.6f}</td>
            <td>
                <a href="/api/runs/{r.id}/report" target="_blank" class="btn">View HTML Report</a>
            </td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>EvalForge - Model Evaluation Harness</title>
      <style>
        body {{ background: #0f172a; color: #f8fafc; font-family: system-ui, sans-serif; padding: 2rem; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        h1 {{ margin-bottom: 0.5rem; }}
        .subtitle {{ color: #94a3b8; margin-bottom: 2rem; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 1.5rem; background: #1e293b; border-radius: 8px; overflow: hidden; }}
        th, td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ background: #090d16; font-size: 0.8rem; text-transform: uppercase; color: #94a3b8; }}
        .btn {{ background: #0284c7; color: white; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-size: 0.85rem; border: none; cursor: pointer; }}
        .btn:hover {{ background: #0369a1; }}
        .badge {{ padding: 4px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: bold; }}
        .badge-success {{ background: rgba(16, 185, 129, 0.2); color: #34d399; }}
        .actions {{ margin-top: 2rem; display: flex; gap: 1rem; align-items: center; }}
      </style>
    </head>
    <body>
      <div class="container">
        <h1>EvalForge Evaluation Platform</h1>
        <p class="subtitle">Provider-agnostic LLM experiment harness, tolerant scoring, and CI regression gating</p>
        
        <h2>Recorded Evaluation Runs</h2>
        <table>
          <thead>
            <tr>
              <th>Experiment</th>
              <th>Run ID</th>
              <th>Status</th>
              <th>Score</th>
              <th>Cases</th>
              <th>Cost</th>
              <th>Artifact</th>
            </tr>
          </thead>
          <tbody>
            {rows if rows else "<tr><td colspan='7' style='text-align:center;'>No runs yet. Use CLI or Demo Reset to seed.</td></tr>"}
          </tbody>
        </table>

        <div class="actions">
          <form action="/api/demo/reset" method="post" onsubmit="event.preventDefault(); fetch('/api/demo/reset', {{method: 'POST', headers: {{'X-Demo-Key': '{settings.demo_admin_key}'}}}}).then(r=>r.json()).then(d=>{{alert('Reset complete!'); location.reload();}});">
            <button type="submit" class="btn" style="background: #dc2626;">Reset Demo State</button>
          </form>
          <span style="color: #64748b; font-size: 0.85rem;">Demo Mode: {settings.demo_mode} (Header: <code>X-Demo-Key: {settings.demo_admin_key}</code>)</span>
        </div>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
