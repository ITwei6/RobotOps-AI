from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Literal, Optional

from typing_extensions import TypedDict


class ToolRequest(TypedDict, total=False):
    tool_name: Literal["log_context", "source_search", "case_search", "knowledge_search"]
    reason: str
    args: Dict[str, Any]


class ToolObservation(TypedDict, total=False):
    tool_name: str
    ok: bool
    args: Dict[str, Any]
    result: Dict[str, Any]
    error: str


class Hypothesis(TypedDict, total=False):
    name: str
    suspected_module: str
    summary: str
    causes: List[str]
    evidence_log_refs: List[int]
    evidence_source_refs: List[int]
    confidence: float


class ModuleRelation(TypedDict, total=False):
    from_module: str
    to_module: str
    reason: str
    evidence_type: Literal["log", "source"]
    evidence_refs: List[str]
    time_delta_ms: int
    source_log_ref: str
    target_log_ref: str


class GraphTraceEvent(TypedDict, total=False):
    node: str
    event: str
    detail: str


class DiagnosisPlan(TypedDict, total=False):
    phase: Literal["collect_logs", "search_source", "retrieve_cases", "retrieve_knowledge", "generate_report", "human_review"]
    reason: str
    tool_requests: List[ToolRequest]


class DiagnosisState(TypedDict, total=False):
    request: Dict[str, Any]
    bug: Dict[str, Any]

    log_evidence: Annotated[List[Dict[str, Any]], operator.add]
    source_evidence: Annotated[List[Dict[str, Any]], operator.add]
    history_cases: Annotated[List[Dict[str, Any]], operator.add]
    knowledge_items: Annotated[List[Dict[str, Any]], operator.add]
    hypotheses: Annotated[List[Hypothesis], operator.add]
    module_relations: Annotated[List[ModuleRelation], operator.add]
    observations: Annotated[List[ToolObservation], operator.add]
    trace: Annotated[List[GraphTraceEvent], operator.add]
    errors: Annotated[List[str], operator.add]

    rule_report: Optional[Dict[str, Any]]
    report: Optional[Dict[str, Any]]
    plan: Optional[DiagnosisPlan]

    llm_enabled: bool
    tool_iteration: int
    max_tool_iterations: int
    confidence: float
    next_route: Literal["plan", "tools", "report", "human_review", "end"]
