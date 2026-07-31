from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from agent_service.app.llm.deepseek import DeepSeekUnavailable, generate_structured_report
from agent_service.app.models import DiagnosisReport
from agent_service.app.rules import diagnose
from agent_service.app.settings import load_settings
from agent_service.app.source_registry import load_repositories
from agent_service.app.tools import fetch_log_context, search_cases, search_knowledge, search_source
from agent_service.app.workflow.confidence import calibrate_report_confidence
from agent_service.app.workflow.state import DiagnosisState, GraphTraceEvent, Hypothesis, ToolObservation, ToolRequest


def normalize_input_node(state: DiagnosisState) -> DiagnosisState:
    request = deepcopy(state.get("request", {}))
    settings = load_settings()
    return {
        "request": request,
        "bug": dict(request.get("bug") or {}),
        "log_evidence": _unique_logs(request.get("logs") or []),
        "source_evidence": _unique_sources(request.get("sources") or []),
        "history_cases": list(request.get("history_cases") or []),
        "knowledge_items": _knowledge_items(request.get("knowledge") or []),
        "llm_enabled": settings.llm_enabled,
        "tool_iteration": 0,
        "max_tool_iterations": settings.max_tool_iterations,
        "confidence": 0.0,
        "next_route": "plan",
        "trace": [_trace("normalize_input", "ok", "normalized diagnose request")],
    }


def rule_evidence_node(state: DiagnosisState) -> DiagnosisState:
    request = _request_with_state_evidence(state)
    report = diagnose(request)
    hypotheses = _hypotheses_from_report(report)
    return {
        "rule_report": report,
        "log_evidence": _unique_logs(report.get("evidence_logs") or []),
        "source_evidence": _unique_sources(report.get("evidence_sources") or []),
        "hypotheses": hypotheses,
        "confidence": float(report.get("confidence") or 0.0),
        "trace": [_trace("rule_evidence", "ok", "rule-template-v1 diagnosis completed")],
    }


def planner_node(state: DiagnosisState) -> DiagnosisState:
    bug = state.get("bug", {})
    if not bug.get("occurred_time") or not bug.get("robot_type"):
        return _plan("human_review", "Bug 缺少 occurred_time 或 robot_type，不能继续自动取证。", [])

    if not state.get("log_evidence") and bug.get("log_package_id") and _can_use_more_tools(state):
        return _plan(
            "collect_logs",
            "当前没有日志证据，先按发生时间从 log-service 获取上下文。",
            [
                {
                    "tool_name": "log_context",
                    "reason": "获取 occurred_time 前后 interaction 日志上下文。",
                    "args": {
                        "bug_id": bug.get("bug_id", ""),
                        "log_package_id": bug.get("log_package_id", ""),
                        "occurred_time": bug.get("occurred_time", 0),
                        "module_name": bug.get("main_module", "interaction"),
                        "seconds_before": 300,
                        "seconds_after": 300,
                        "keywords": ["touch", "self check", "TaskFactory", "WorkerManager", "Skill"],
                    },
                }
            ],
        )

    if (
        state.get("log_evidence")
        and not state.get("source_evidence")
        and not _tool_was_attempted(state, "source_search")
        and _can_use_more_tools(state)
    ):
        return _plan(
            "search_source",
            "已有日志证据但缺少源码证据，检索 interaction 关键源码位置。",
            [
                {
                    "tool_name": "source_search",
                    "reason": "根据日志关键句定位 interaction 源码。",
                    "args": {
                        "module_name": bug.get("main_module", "interaction"),
                        "branch": bug.get("branch", ""),
                        "commit": bug.get("commit", ""),
                        "keywords": _keywords_from_logs(state.get("log_evidence") or []),
                        "max_results": 10,
                    },
                }
            ],
        )

    if not state.get("history_cases") and not _tool_was_attempted(state, "case_search") and _can_use_more_tools(state):
        return _plan(
            "retrieve_cases",
            "已有基础证据，检索相似 interaction 历史案例作为参考。",
            [
                {
                    "tool_name": "case_search",
                    "reason": "用 Bug 描述、机器人类型、模块和日志关键句匹配已确认案例。",
                    "args": {
                        "title": bug.get("title", ""),
                        "description": bug.get("description", ""),
                        "robot_type": bug.get("robot_type", ""),
                        "main_module": bug.get("main_module", ""),
                        "keywords": _keywords_from_logs(state.get("log_evidence") or []),
                        "max_results": 5,
                    },
                }
            ],
        )

    if not state.get("knowledge_items") and not _tool_was_attempted(state, "knowledge_search") and _can_use_more_tools(state):
        return _plan(
            "retrieve_knowledge",
            "案例检索完成，继续检索相关 SOP、错误码和模块知识。",
            [
                {
                    "tool_name": "knowledge_search",
                    "reason": "根据 Bug 描述、模块和日志关键词检索可引用的排障知识。",
                    "args": {
                        "title": bug.get("title", ""),
                        "description": bug.get("description", ""),
                        "main_module": bug.get("main_module", ""),
                        "keywords": _keywords_from_logs(state.get("log_evidence") or []),
                        "max_results": 5,
                    },
                }
            ],
        )

    return _plan("generate_report", "已有证据可以生成结构化诊断报告。", [])


def tool_executor_node(state: DiagnosisState) -> DiagnosisState:
    plan = state.get("plan") or {}
    observations: List[ToolObservation] = []
    errors: List[str] = []
    for request in plan.get("tool_requests") or []:
        observation = _execute_tool(request)
        observations.append(observation)
        if not observation.get("ok"):
            errors.append(str(observation.get("error") or "tool execution failed"))

    return {
        "observations": observations,
        "tool_iteration": int(state.get("tool_iteration") or 0) + 1,
        "errors": errors,
        "trace": [_trace("tool_executor", "ok", f"executed {len(observations)} tool request(s)")],
    }


def observation_analyzer_node(state: DiagnosisState) -> DiagnosisState:
    logs: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []
    history_cases: List[Dict[str, Any]] = []
    knowledge_items: List[Dict[str, Any]] = []
    for observation in state.get("observations") or []:
        if not observation.get("ok"):
            continue
        result = observation.get("result") or {}
        logs.extend(result.get("logs") or [])
        sources.extend(result.get("sources") or [])
        history_cases.extend(result.get("history_cases") or [])
        knowledge_items.extend(result.get("knowledge_items") or [])

    next_route = "report"
    combined_sources = list(state.get("source_evidence") or []) + sources
    if _can_use_more_tools(state) and _needs_more_tool_pass(state, logs, combined_sources):
        next_route = "plan"

    return {
        "log_evidence": _unique_logs(logs),
        "source_evidence": _unique_sources(sources),
        "history_cases": history_cases,
        "knowledge_items": knowledge_items,
        "next_route": next_route,
        "trace": [_trace("observation_analyzer", "ok", "converted observations to evidence")],
    }


def choose_report_node(state: DiagnosisState) -> DiagnosisState:
    detail = "llm report enabled" if state.get("llm_enabled") else "llm disabled, use fallback report"
    return {"next_route": "report", "trace": [_trace("choose_report", "ok", detail)]}


def llm_report_node(state: DiagnosisState) -> DiagnosisState:
    settings = load_settings()
    rule_report = diagnose(_request_with_state_evidence(state))
    try:
        report = generate_structured_report(
            model=settings.llm_model,
            request=_request_with_state_evidence(state),
            rule_report=rule_report,
        )
        report = _merge_report_evidence(report, rule_report)
        report["agent_version"] = "langgraph-diagnosis-v1"
        return {
            "report": DiagnosisReport(**report).model_dump(),
            "trace": [_trace("llm_report", "ok", f"generated report with {settings.llm_model}")],
        }
    except Exception as exc:
        return {
            "errors": [f"llm_report failed: {exc}"],
            "next_route": "human_review",
            "trace": [_trace("llm_report", "fallback", "llm failed, use fallback report")],
        }


def fallback_report_node(state: DiagnosisState) -> DiagnosisState:
    report = diagnose(_request_with_state_evidence(state))
    _merge_history_context(report, state.get("history_cases") or [])
    _merge_knowledge_context(report, state.get("knowledge_items") or [])
    report["agent_version"] = "langgraph-diagnosis-v1"
    return {
        "report": DiagnosisReport(**report).model_dump(),
        "trace": [_trace("fallback_report", "ok", "using rule baseline report")],
    }


def confidence_check_node(state: DiagnosisState) -> DiagnosisState:
    report = dict(state.get("report") or state.get("rule_report") or _empty_report(state))
    calibrated = calibrate_report_confidence(
        report,
        state.get("log_evidence") or [],
        state.get("source_evidence") or [],
        state.get("errors") or [],
    )
    return {
        "report": DiagnosisReport(**calibrated).model_dump(),
        "confidence": float(calibrated.get("confidence") or 0.0),
        "trace": [_trace("confidence_check", "ok", "calibrated diagnosis confidence")],
    }


def finalize_node(state: DiagnosisState) -> DiagnosisState:
    report = dict(state.get("report") or state.get("rule_report") or _empty_report(state))
    report["agent_version"] = "langgraph-diagnosis-v1"
    report.setdefault("status", "TASK_STATUS_SUCCEEDED")
    return {
        "report": DiagnosisReport(**report).model_dump(),
        "next_route": "end",
        "trace": [_trace("finalize", "ok", "final report ready")],
    }


def _execute_tool(request: ToolRequest) -> ToolObservation:
    tool_name = str(request.get("tool_name") or "")
    args = dict(request.get("args") or {})
    settings = load_settings()
    if tool_name == "log_context":
        result = fetch_log_context(
            log_service_url=settings.log_service_url,
            timeout_seconds=settings.tool_timeout_seconds,
            args=args,
        )
        return _tool_observation(tool_name, args, result, "logs")
    if tool_name == "source_search":
        result = search_source(
            roots=settings.source_search_roots,
            timeout_seconds=settings.tool_timeout_seconds,
            args=args,
            workspace_root=settings.source_workspace_root,
            repositories=load_repositories(settings.source_repository_file),
        )
        return _tool_observation(tool_name, args, result, "sources")
    if tool_name == "case_search":
        result = search_cases(settings.case_search_roots, args)
        return _tool_observation(tool_name, args, result, "history_cases")
    if tool_name == "knowledge_search":
        result = search_knowledge(settings.knowledge_search_roots, args)
        return _tool_observation(tool_name, args, result, "knowledge_items")
    return {"tool_name": tool_name, "ok": False, "args": args, "result": {}, "error": f"unknown tool: {tool_name}"}


def _merge_report_evidence(report: Dict[str, Any], rule_report: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(report)
    merged["evidence_logs"] = _unique_logs(
        list(merged.get("evidence_logs") or []) + list(rule_report.get("evidence_logs") or [])
    )
    merged["evidence_sources"] = _unique_sources(
        list(merged.get("evidence_sources") or []) + list(rule_report.get("evidence_sources") or [])
    )

    questions = list(merged.get("questions_for_human") or [])
    for question in rule_report.get("questions_for_human") or []:
        if question not in questions:
            questions.append(question)
    merged["questions_for_human"] = questions

    if not merged.get("possible_causes"):
        merged["possible_causes"] = list(rule_report.get("possible_causes") or [])
    if not merged.get("recommended_actions"):
        merged["recommended_actions"] = list(rule_report.get("recommended_actions") or [])
    if not merged.get("suspected_module"):
        merged["suspected_module"] = str(rule_report.get("suspected_module") or "unknown")
    if not merged.get("summary"):
        merged["summary"] = str(rule_report.get("summary") or "当前证据不足，无法生成明确结论。")
    return merged


def _merge_history_context(report: Dict[str, Any], cases: List[Dict[str, Any]]) -> None:
    """Expose case-derived suggestions as references, without treating them as proof."""
    for case in cases[:3]:
        case_id = str(case.get("case_id") or case.get("id") or "unknown")
        for field in ("causes", "possible_causes"):
            for value in case.get(field) or []:
                item = f"历史案例参考原因（{case_id}）：{value}"
                if item not in report["possible_causes"]:
                    report["possible_causes"].append(item)
        for field in ("actions", "recommended_actions"):
            for value in case.get(field) or []:
                item = f"历史案例参考建议（{case_id}）：{value}"
                if item not in report["recommended_actions"]:
                    report["recommended_actions"].append(item)


def _merge_knowledge_context(report: Dict[str, Any], items: List[Dict[str, Any]]) -> None:
    for item in items[:3]:
        source = str(item.get("source") or item.get("source_id") or "unknown")
        content = str(item.get("content") or item.get("summary") or "").strip()
        if not content:
            continue
        reference = f"知识库参考（{source}）：{content}"
        if reference not in report["recommended_actions"]:
            report["recommended_actions"].append(reference)


def _tool_observation(tool_name: str, args: Dict[str, Any], result: Dict[str, Any], result_key: str) -> ToolObservation:
    ok = bool(result.get("ok"))
    payload = {result_key: list(result.get(result_key) or [])}
    observation: ToolObservation = {"tool_name": tool_name, "ok": ok, "args": args, "result": payload}
    if not ok:
        observation["error"] = str(result.get("error") or f"{tool_name} failed")
    return observation


def _request_with_state_evidence(state: DiagnosisState) -> Dict[str, Any]:
    request = deepcopy(state.get("request", {}))
    request["logs"] = _unique_logs(list(request.get("logs") or []) + list(state.get("log_evidence") or []))
    request["sources"] = _unique_sources(list(request.get("sources") or []) + list(state.get("source_evidence") or []))
    request["history_cases"] = list(request.get("history_cases") or []) + list(state.get("history_cases") or [])
    request["knowledge"] = list(request.get("knowledge") or []) + list(state.get("knowledge_items") or [])
    return request


def _plan(phase: str, reason: str, tool_requests: List[ToolRequest]) -> DiagnosisState:
    next_route = "tools" if tool_requests else "report"
    if phase == "human_review":
        next_route = "human_review"
    return {
        "plan": {"phase": phase, "reason": reason, "tool_requests": tool_requests},
        "next_route": next_route,
        "trace": [_trace("planner", "ok", reason)],
    }


def _hypotheses_from_report(report: Dict[str, Any]) -> List[Hypothesis]:
    return [
        {
            "name": "rule_baseline",
            "suspected_module": str(report.get("suspected_module", "")),
            "summary": str(report.get("summary", "")),
            "causes": list(report.get("possible_causes") or []),
            "evidence_log_refs": list(range(len(report.get("evidence_logs") or []))),
            "evidence_source_refs": list(range(len(report.get("evidence_sources") or []))),
            "confidence": float(report.get("confidence") or 0.0),
        }
    ]


def _empty_report(state: DiagnosisState) -> Dict[str, Any]:
    bug = state.get("bug", {})
    return {
        "summary": "当前证据不足，Agent 工作流无法给出高置信度结论。",
        "suspected_module": str(bug.get("main_module") or "unknown"),
        "possible_causes": ["需要补充发生时间窗口内的 interaction、mc、hds、sm、agent 日志后再判断。"],
        "evidence_logs": [],
        "evidence_sources": [],
        "recommended_actions": ["确认 Bug 发生时间、机器人类型和日志包是否完整。"],
        "confidence": 0.15,
        "questions_for_human": [
            "飞书工单中的发生时间是否准确？",
            "日志包是否包含 interaction、mc、hds、sm、agent 等关键模块？",
        ],
        "agent_version": "langgraph-diagnosis-v1",
        "status": "TASK_STATUS_SUCCEEDED",
    }


def _can_use_more_tools(state: DiagnosisState) -> bool:
    return int(state.get("tool_iteration") or 0) < int(state.get("max_tool_iterations") or 0)


def _tool_was_attempted(state: DiagnosisState, tool_name: str) -> bool:
    return any(observation.get("tool_name") == tool_name for observation in state.get("observations") or [])


def _needs_more_tool_pass(
    state: DiagnosisState,
    observed_logs: List[Dict[str, Any]],
    observed_sources: List[Dict[str, Any]],
) -> bool:
    bug = state.get("bug", {})
    has_logs = bool(state.get("log_evidence") or observed_logs)
    has_sources = bool(state.get("source_evidence") or observed_sources)
    if not has_logs and bug.get("log_package_id") and not _tool_was_attempted(state, "log_context"):
        return True
    if has_logs and not has_sources and not _tool_was_attempted(state, "source_search"):
        return True
    if not _tool_was_attempted(state, "case_search"):
        return True
    if not _tool_was_attempted(state, "knowledge_search"):
        return True
    return False


def _keywords_from_logs(logs: List[Dict[str, Any]]) -> List[str]:
    keywords: List[str] = []
    for log in logs[:10]:
        message = str(log.get("message") or log.get("raw_line") or "")
        if message:
            keywords.append(message[:120])
    return keywords[:5]


def _unique_logs(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen = set()
    for log in logs:
        key = (
            str(log.get("module_name", "")),
            str(log.get("file_name", "")),
            int(log.get("line_no") or 0),
            str(log.get("raw_line") or log.get("message") or ""),
        )
        if key in seen:
            continue
        result.append(dict(log))
        seen.add(key)
    return result


def _unique_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen = set()
    for source in sources:
        key = (
            str(source.get("repo", "")),
            str(source.get("file_path", "")),
            str(source.get("function_name", "")),
            str(source.get("matched_text", "")),
        )
        if key in seen:
            continue
        result.append(dict(source))
        seen.add(key)
    return result


def _knowledge_items(values: List[Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for value in values:
        if isinstance(value, dict):
            result.append(dict(value))
        else:
            result.append({"content": str(value)})
    return result


def _trace(node: str, event: str, detail: str) -> GraphTraceEvent:
    return {"node": node, "event": event, "detail": detail}
