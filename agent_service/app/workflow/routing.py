from __future__ import annotations

from agent_service.app.workflow.state import DiagnosisState


def route_after_plan(state: DiagnosisState) -> str:
    route = state.get("next_route", "report")
    if route == "tools":
        return "tools"
    if route == "human_review":
        return "human_review"
    return "report"


def route_after_observation(state: DiagnosisState) -> str:
    route = state.get("next_route", "report")
    if route == "plan":
        return "plan"
    if route == "human_review":
        return "human_review"
    return "report"


def route_after_choose_report(state: DiagnosisState) -> str:
    return "llm" if state.get("llm_enabled") else "fallback"


def route_after_llm(state: DiagnosisState) -> str:
    return "fallback" if state.get("next_route") == "human_review" else "ok"
