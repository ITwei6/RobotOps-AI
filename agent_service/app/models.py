from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class BugContext(BaseModel):
    bug_id: str = ""
    title: str
    description: str
    robot_type: str
    main_module: str
    occurred_time: int
    software_version: str = ""
    branch: str = ""
    commit: str = ""
    log_package_id: str = ""
    # Deprecated compatibility field. Repository ownership belongs to the platform registry.
    source_repo: str = ""


class LogEvidence(BaseModel):
    module_name: str
    file_name: str = ""
    line_no: int = 0
    log_time: int = 0
    log_level: str = ""
    message: str = ""
    raw_line: str = ""
    trace_id: str = ""
    task_id: str = ""
    session_id: str = ""


class SourceEvidence(BaseModel):
    repo: str = ""
    branch: str = ""
    commit: str = ""
    file_path: str
    function_name: str = ""
    matched_text: str = ""
    snippet: str = ""


class EvidenceClaim(BaseModel):
    claim: str
    evidence_refs: List[str] = Field(default_factory=list)
    support_level: Literal["confirmed", "likely", "unknown"] = "unknown"
    confidence: float = 0.0


class DiagnoseRequest(BaseModel):
    bug: BugContext
    logs: List[LogEvidence] = Field(default_factory=list)
    sources: List[SourceEvidence] = Field(default_factory=list)
    history_cases: List[Dict[str, Any]] = Field(default_factory=list)
    knowledge: List[str] = Field(default_factory=list)


class DiagnosisReport(BaseModel):
    summary: str
    suspected_module: str
    possible_causes: List[str]
    execution_chain: List[str] = Field(default_factory=list)
    module_relations: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_logs: List[LogEvidence]
    evidence_sources: List[SourceEvidence]
    evidence_claims: List[EvidenceClaim] = Field(default_factory=list)
    recommended_actions: List[str]
    confidence: float
    questions_for_human: List[str]
    agent_version: str = "rule-template-v1"
    generation_mode: str = "deterministic_fallback"
    generation_detail: str = ""
    trace_id: str = ""
    diagnostic_trace: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "TASK_STATUS_SUCCEEDED"


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "agent-service"
    version: str = "0.1.0"


class ErrorResponse(BaseModel):
    detail: Optional[str] = None


class SourceRepositoryConfig(BaseModel):
    repo_url: str
    branch: str = ""
    commit: str = ""
    local_path: str = ""
