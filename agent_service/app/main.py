from __future__ import annotations

from fastapi import FastAPI

from agent_service.app.models import DiagnoseRequest, DiagnosisReport, HealthResponse
from agent_service.app.workflow import run_diagnosis_workflow


app = FastAPI(
    title="RobotOps AI Agent Service",
    version="0.1.0",
    description="Rule-template diagnosis agent for robot interaction bug analysis.",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/diagnose", response_model=DiagnosisReport)
def diagnose_bug(request: DiagnoseRequest) -> DiagnosisReport:
    report = run_diagnosis_workflow(request.model_dump())
    return DiagnosisReport(**report)
