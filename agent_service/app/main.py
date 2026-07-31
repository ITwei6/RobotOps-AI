from __future__ import annotations

from fastapi import FastAPI

from agent_service.app.models import DiagnoseRequest, DiagnosisReport, HealthResponse, SourceRepositoryConfig
from agent_service.app.settings import load_settings
from agent_service.app.source_registry import load_repositories, save_repository
from agent_service.app.workflow import run_diagnosis_workflow


app = FastAPI(
    title="RobotOps AI Agent Service",
    version="0.1.0",
    description="Evidence-driven diagnosis agent for multi-module robot software bugs.",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/diagnose", response_model=DiagnosisReport)
def diagnose_bug(request: DiagnoseRequest) -> DiagnosisReport:
    report = run_diagnosis_workflow(request.model_dump())
    return DiagnosisReport(**report)


@app.get("/source-repositories")
def list_source_repositories() -> dict:
    return {"repositories": load_repositories(load_settings().source_repository_file)}


@app.put("/source-repositories/{module_name}")
def update_source_repository(module_name: str, config: SourceRepositoryConfig) -> dict:
    module = module_name.strip()
    if not module:
        return {"ok": False, "error": "module_name is required"}
    saved = save_repository(load_settings().source_repository_file, module, config.model_dump())
    return {"ok": True, "module_name": module, "repository": saved}
