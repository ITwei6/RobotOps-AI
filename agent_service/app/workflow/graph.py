from __future__ import annotations

from typing import Any, Dict

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:  # pragma: no cover - keeps a deterministic fallback for minimal installs.
    END = START = StateGraph = None

from agent_service.app.models import DiagnosisReport
from agent_service.app.workflow.nodes import (
    choose_report_node,
    confidence_check_node,
    fallback_report_node,
    finalize_node,
    llm_report_node,
    normalize_input_node,
    observation_analyzer_node,
    planner_node,
    rule_evidence_node,
    tool_executor_node,
)
from agent_service.app.workflow.routing import (
    route_after_choose_report,
    route_after_llm,
    route_after_observation,
    route_after_plan,
)
from agent_service.app.workflow.state import DiagnosisState


def build_diagnosis_graph():
    if StateGraph is None:
        return _SequentialDiagnosisGraph()

    builder = StateGraph(DiagnosisState)
    builder.add_node("normalize_input", normalize_input_node)
    builder.add_node("rule_evidence", rule_evidence_node)
    builder.add_node("planner", planner_node)
    builder.add_node("tool_executor", tool_executor_node)
    builder.add_node("observation_analyzer", observation_analyzer_node)
    builder.add_node("choose_report", choose_report_node)
    builder.add_node("llm_report", llm_report_node)
    builder.add_node("fallback_report", fallback_report_node)
    builder.add_node("confidence_check", confidence_check_node)
    builder.add_node("finalize", finalize_node)

    builder.add_edge(START, "normalize_input")
    builder.add_edge("normalize_input", "rule_evidence")
    builder.add_edge("rule_evidence", "planner")
    builder.add_conditional_edges(
        "planner",
        route_after_plan,
        {"tools": "tool_executor", "report": "choose_report", "human_review": "fallback_report"},
    )
    builder.add_edge("tool_executor", "observation_analyzer")
    builder.add_conditional_edges(
        "observation_analyzer",
        route_after_observation,
        {"plan": "planner", "report": "choose_report", "human_review": "fallback_report"},
    )
    builder.add_conditional_edges(
        "choose_report",
        route_after_choose_report,
        {"llm": "llm_report", "fallback": "fallback_report"},
    )
    builder.add_conditional_edges("llm_report", route_after_llm, {"ok": "confidence_check", "fallback": "fallback_report"})
    builder.add_edge("fallback_report", "confidence_check")
    builder.add_edge("confidence_check", "finalize")
    builder.add_edge("finalize", END)
    return builder.compile()


def run_diagnosis_workflow(request: Dict[str, Any]) -> Dict[str, Any]:
    graph = build_diagnosis_graph()
    final_state = graph.invoke({"request": request})
    report = final_state.get("report") or {}
    return DiagnosisReport(**report).model_dump()


class _SequentialDiagnosisGraph:
    def invoke(self, initial_state: DiagnosisState) -> DiagnosisState:
        state: DiagnosisState = dict(initial_state)
        self._merge(state, normalize_input_node(state))
        self._merge(state, rule_evidence_node(state))

        while True:
            self._merge(state, planner_node(state))
            route = route_after_plan(state)
            if route != "tools":
                break
            self._merge(state, tool_executor_node(state))
            self._merge(state, observation_analyzer_node(state))
            if route_after_observation(state) != "plan":
                break

        route = route_after_plan(state)
        if route == "human_review":
            self._merge(state, fallback_report_node(state))
        else:
            self._merge(state, choose_report_node(state))
            if route_after_choose_report(state) == "llm":
                self._merge(state, llm_report_node(state))
                if route_after_llm(state) == "fallback":
                    self._merge(state, fallback_report_node(state))
            else:
                self._merge(state, fallback_report_node(state))

        self._merge(state, confidence_check_node(state))
        self._merge(state, finalize_node(state))
        return state

    def _merge(self, state: DiagnosisState, update: DiagnosisState) -> None:
        append_keys = {
            "log_evidence",
            "source_evidence",
            "history_cases",
            "knowledge_items",
            "hypotheses",
            "module_relations",
            "observations",
            "trace",
            "errors",
        }
        for key, value in update.items():
            if key in append_keys:
                state[key] = list(state.get(key) or []) + list(value or [])
            else:
                state[key] = value
