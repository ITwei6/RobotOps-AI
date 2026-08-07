from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Dict, List
from uuid import uuid4

from agent_service.app.llm.deepseek import DeepSeekUnavailable, generate_structured_report
from agent_service.app.llm.source_planner import (
    SourcePlanningUnavailable,
    build_deterministic_source_investigation,
    generate_source_investigation,
    ground_source_investigation,
)
from agent_service.app.langchain_tools import build_tool_registry
from agent_service.app.models import DiagnosisReport
from agent_service.app.rules import diagnose
from agent_service.app.settings import load_settings
from agent_service.app.source_queries import build_source_queries
from agent_service.app.source_registry import load_repositories
from agent_service.app.tools import fetch_log_context, search_cases, search_knowledge, search_source
from agent_service.app.workflow.confidence import calibrate_report_confidence
from agent_service.app.workflow.state import DiagnosisState, GraphTraceEvent, Hypothesis, ToolObservation, ToolRequest


AGENT_VERSION = "langgraph-diagnosis-v3"


def normalize_input_node(state: DiagnosisState) -> DiagnosisState:
    request = deepcopy(state.get("request", {}))
    settings = load_settings()
    return {
        "request": request,
        "bug": dict(request.get("bug") or {}),
        "trace_id": uuid4().hex,
        "log_evidence": _unique_logs(request.get("logs") or []),
        "source_evidence": _unique_sources(request.get("sources") or []),
        "module_relations": [],
        "history_cases": list(request.get("history_cases") or []),
        "knowledge_items": _knowledge_items(request.get("knowledge") or []),
        "llm_enabled": settings.llm_enabled,
        "tool_iteration": 0,
        "max_tool_iterations": settings.max_tool_iterations,
        "source_analysis_cursor": 0,
        "source_analysis_iteration": 0,
        "max_source_analysis_iterations": settings.max_source_analysis_iterations,
        "source_investigation": None,
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
        "module_relations": _derive_module_relations(state, report.get("evidence_logs") or [], report.get("evidence_sources") or []),
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
            "当前没有日志证据，先按发生时间从 log-service 获取全部模块上下文。",
            [
                {
                    "tool_name": "log_context",
                    "reason": "获取 occurred_time 前后全部模块日志上下文。",
                    "args": {
                        "bug_id": bug.get("bug_id", ""),
                        "log_package_id": bug.get("log_package_id", ""),
                        "occurred_time": bug.get("occurred_time", 0),
                        # An empty module filter lets log-service return all
                        # modules in the same time window for correlation.
                        "module_name": "",
                        "seconds_before": 300,
                        "seconds_after": 300,
                        "keywords": [],
                    },
                }
            ],
        )

    followup = _next_source_followup(state)
    if followup and _can_use_more_tools(state):
        return _plan(
            "search_source",
            f"继续验证源码上下文中的调用符号 {followup['query']}。",
            [
                {
                    "tool_name": "source_search",
                    "reason": str(followup.get("reason") or "继续追踪源码调用链。"),
                    "args": {
                        "module_name": followup["module_name"],
                        "branch": bug.get("branch", ""),
                        "commit": bug.get("commit", ""),
                        "keywords": [followup["query"]],
                        "max_results": 3,
                    },
                }
            ],
        )

    modules = _next_source_modules(state)
    if modules and _can_use_more_tools(state):
        return _plan(
            "search_source",
            "先分析主模块源码，再根据主链路证据按需深入关联模块源码。",
            [
                {
                    "tool_name": "source_search",
                    "reason": f"根据日志关键句定位 {module} 模块源码。",
                    "args": {
                        "module_name": module,
                        "branch": bug.get("branch", ""),
                        "commit": bug.get("commit", ""),
                        "keywords": build_source_queries(
                            bug=bug,
                            logs=state.get("log_evidence") or [],
                            module_name=module,
                        ),
                        "max_results": 6,
                    },
                }
                for module in modules[:1]
            ],
        )

    if not state.get("history_cases") and not _tool_was_attempted(state, "case_search") and _can_use_more_tools(state):
        return _plan(
            "retrieve_cases",
            "已有基础证据，检索相似模块历史案例作为参考。",
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
    relations = _derive_module_relations(state, logs, sources)
    previous_logs = _unique_logs(state.get("log_evidence") or [])
    previous_sources = _unique_sources(state.get("source_evidence") or [])
    new_logs = _unique_logs(logs)
    new_sources = _unique_sources(sources)
    log_keys = {_log_key(item) for item in previous_logs}
    source_keys = {_source_key(item) for item in previous_sources}
    has_new_evidence = any(_log_key(item) not in log_keys for item in new_logs)
    has_new_evidence = has_new_evidence or any(_source_key(item) not in source_keys for item in new_sources)
    has_new_evidence = has_new_evidence or bool(history_cases) or bool(knowledge_items)
    needs_more_tools = _needs_more_tool_pass(state, logs, combined_sources)
    if _can_use_more_tools(state) and needs_more_tools:
        next_route = "plan"
    elif not has_new_evidence and state.get("observations"):
        next_route = "report"

    return {
        "log_evidence": _unique_logs(logs),
        "source_evidence": _unique_sources(sources),
        "history_cases": history_cases,
        "knowledge_items": knowledge_items,
        "module_relations": relations,
        "next_route": next_route,
        "trace": [_trace(
            "observation_analyzer",
            "ok",
            "converted observations to evidence" if has_new_evidence else "no new evidence; stop tool loop",
        )],
    }


def source_analysis_node(state: DiagnosisState) -> DiagnosisState:
    sources = _unique_sources(state.get("source_evidence") or [])
    cursor = int(state.get("source_analysis_cursor") or 0)
    if len(sources) <= cursor:
        return {
            "next_route": "plan" if _can_use_more_tools(state) and _needs_more_tool_pass(
                state, [], sources
            ) else "report",
            "trace": [_trace("source_analysis", "skip", "no new source evidence")],
        }

    iteration = int(state.get("source_analysis_iteration") or 0)
    max_iterations = int(state.get("max_source_analysis_iterations") or 0)
    if iteration >= max_iterations:
        return {
            "source_analysis_cursor": len(sources),
            "source_investigation": {
                "queries": [],
                "stop": True,
                "stop_reason": "已达到源码分析最大轮次。",
                "planning_mode": "deterministic",
                "rejected_query_count": 0,
            },
            "trace": [_trace("source_analysis", "stop", "source analysis iteration limit reached")],
        }

    new_sources = sources[cursor:]
    module_name = _latest_source_module(state) or str(state.get("bug", {}).get("main_module") or "")
    registered_relations = _registered_source_relations(state, module_name, new_sources)
    allowed_modules = _allowed_source_followup_modules(state, module_name, registered_relations)
    attempted_queries = _attempted_source_queries(state)
    settings = load_settings()
    planning_mode = "deterministic"
    fallback_reason = ""

    if state.get("llm_enabled"):
        try:
            raw_plan = generate_source_investigation(
                model=settings.llm_model,
                bug=state.get("bug", {}),
                logs=_unique_logs(state.get("log_evidence") or []),
                sources=sources,
                allowed_modules=allowed_modules,
                attempted_queries=attempted_queries,
            )
            investigation = ground_source_investigation(
                raw_plan,
                sources=sources,
                allowed_modules=allowed_modules,
                attempted_queries=attempted_queries,
            )
            planning_mode = "deepseek"
            if not investigation.get("stop") and not investigation.get("queries"):
                fallback_reason = "DeepSeek queries did not pass evidence grounding"
                investigation = build_deterministic_source_investigation(
                    sources=new_sources,
                    module_name=module_name,
                    allowed_modules=allowed_modules,
                    attempted_queries=attempted_queries,
                )
                planning_mode = "deterministic"
        except (SourcePlanningUnavailable, TypeError, ValueError):
            fallback_reason = "DeepSeek source planning unavailable"
            investigation = build_deterministic_source_investigation(
                sources=new_sources,
                module_name=module_name,
                allowed_modules=allowed_modules,
                attempted_queries=attempted_queries,
            )
    else:
        investigation = build_deterministic_source_investigation(
            sources=new_sources,
            module_name=module_name,
            allowed_modules=allowed_modules,
            attempted_queries=attempted_queries,
        )

    investigation["planning_mode"] = planning_mode
    next_route = "plan" if investigation.get("queries") and _can_use_more_tools(state) else state.get("next_route", "report")
    detail = (
        f"mode={planning_mode}, queries={len(investigation.get('queries') or [])}, "
        f"rejected={int(investigation.get('rejected_query_count') or 0)}, "
        f"stop={bool(investigation.get('stop'))}"
    )
    if fallback_reason:
        detail += f", fallback={fallback_reason}"
    return {
        "source_analysis_cursor": len(sources),
        "source_analysis_iteration": iteration + 1,
        "source_investigation": investigation,
        "module_relations": registered_relations,
        "next_route": next_route,
        "trace": [_trace("source_analysis", "ok", detail)],
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
        report["module_relations"] = _unique_relations(
            list(report.get("module_relations") or []) + list(state.get("module_relations") or [])
        )
        report = _ground_report_claims(report)
        report["agent_version"] = AGENT_VERSION
        report["generation_mode"] = "deepseek"
        report["generation_detail"] = (
            f"structured report generated by {settings.llm_model}; "
            f"{_source_generation_detail(state)}"
        )
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
    report["module_relations"] = _unique_relations(state.get("module_relations") or [])
    report = _ground_report_claims(report)
    report["agent_version"] = AGENT_VERSION
    llm_failed = any("llm_report failed" in str(error) for error in state.get("errors") or [])
    if llm_failed:
        report["generation_mode"] = "llm_fallback"
        report["generation_detail"] = (
            "DeepSeek failed validation or was unavailable; deterministic report used; "
            f"{_source_generation_detail(state)}"
        )
    elif state.get("llm_enabled"):
        report["generation_mode"] = "deterministic_fallback"
        report["generation_detail"] = (
            "LLM path was skipped because evidence collection required fallback; "
            f"{_source_generation_detail(state)}"
        )
    else:
        report["generation_mode"] = "deterministic_fallback"
        report["generation_detail"] = (
            "DeepSeek disabled or API key unavailable; "
            f"{_source_generation_detail(state)}"
        )
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
    calibrated = _ground_report_claims(calibrated)
    return {
        "report": DiagnosisReport(**calibrated).model_dump(),
        "confidence": float(calibrated.get("confidence") or 0.0),
        "trace": [_trace("confidence_check", "ok", "calibrated diagnosis confidence")],
    }


def finalize_node(state: DiagnosisState) -> DiagnosisState:
    report = dict(state.get("report") or state.get("rule_report") or _empty_report(state))
    report["agent_version"] = AGENT_VERSION
    report["trace_id"] = str(state.get("trace_id") or "")
    report["diagnostic_trace"] = _public_trace(
        list(state.get("trace") or [])
        + [_trace("finalize", "ok", "final report ready")]
    )
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
    tools = build_tool_registry(
        log_service_url=settings.log_service_url,
        timeout_seconds=settings.tool_timeout_seconds,
        source_roots=settings.source_search_roots,
        source_workspace_root=settings.source_workspace_root,
        source_index_root=settings.source_index_root,
        source_repository_file=settings.source_repository_file,
        case_roots=settings.case_search_roots,
        knowledge_roots=settings.knowledge_search_roots,
        log_fetcher=fetch_log_context,
        source_searcher=search_source,
        case_searcher=search_cases,
        knowledge_searcher=search_knowledge,
    )
    tool = tools.get(tool_name)
    if tool is None:
        return {"tool_name": tool_name, "ok": False, "args": args, "result": {}, "error": f"unknown tool: {tool_name}"}
    try:
        result = tool.invoke(args)
    except Exception as exc:
        return {
            "tool_name": tool_name,
            "ok": False,
            "args": args,
            "result": {},
            "error": f"{tool_name} invocation failed: {exc}",
        }
    result = result if isinstance(result, dict) else {"value": result}
    result_key = {
        "log_context": "logs",
        "source_search": "sources",
        "case_search": "history_cases",
        "knowledge_search": "knowledge_items",
    }[tool_name]
    return _tool_observation(tool_name, args, result, result_key)


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
    if not merged.get("execution_chain"):
        merged["execution_chain"] = list(rule_report.get("execution_chain") or [])
    if not merged.get("module_relations"):
        merged["module_relations"] = list(rule_report.get("module_relations") or [])
    if not merged.get("recommended_actions"):
        merged["recommended_actions"] = list(rule_report.get("recommended_actions") or [])
    if not merged.get("evidence_claims"):
        merged["evidence_claims"] = list(rule_report.get("evidence_claims") or [])
    if not merged.get("suspected_module"):
        merged["suspected_module"] = str(rule_report.get("suspected_module") or "unknown")
    if not merged.get("summary"):
        merged["summary"] = str(rule_report.get("summary") or "当前证据不足，无法生成明确结论。")
    return merged


def _ground_report_claims(report: Dict[str, Any]) -> Dict[str, Any]:
    """Keep conclusion-to-evidence links valid after LLM/rule report merging."""
    updated = dict(report)
    logs = list(updated.get("evidence_logs") or [])
    sources = list(updated.get("evidence_sources") or [])
    valid_refs = {_log_ref_for_claim(log) for log in logs} | {_source_ref_for_claim(source) for source in sources}
    claims: List[Dict[str, Any]] = []
    for item in updated.get("evidence_claims") or []:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim") or "").strip()
        if not claim:
            continue
        refs = [str(ref).strip() for ref in item.get("evidence_refs") or [] if str(ref).strip() in valid_refs]
        support_level = str(item.get("support_level") or "unknown").strip().lower()
        if support_level not in {"confirmed", "likely", "unknown"}:
            support_level = "unknown"
        try:
            claim_confidence = float(item.get("confidence") or (0.8 if refs else 0.2))
        except (TypeError, ValueError):
            claim_confidence = 0.2
        claims.append({
            "claim": claim,
            "evidence_refs": list(dict.fromkeys(refs))[:10],
            "support_level": support_level if refs or support_level == "unknown" else "unknown",
            "confidence": max(0.0, min(claim_confidence, 1.0)),
        })

    existing = {item["claim"] for item in claims}
    for text in [updated.get("summary", "")] + list(updated.get("possible_causes") or []):
        claim = str(text or "").strip()
        if not claim or claim in existing:
            continue
        refs = _matching_claim_refs(claim, logs, sources)
        claims.append({
            "claim": claim,
            "evidence_refs": refs,
            "support_level": "confirmed" if refs else "unknown",
            "confidence": 0.8 if refs else 0.2,
        })
        existing.add(claim)
    updated["evidence_claims"] = claims[:20]
    return updated


def _matching_claim_refs(claim: str, logs: List[Dict[str, Any]], sources: List[Dict[str, Any]]) -> List[str]:
    stop_words = {
        "当前", "根据", "进行", "已经", "没有", "进入", "但是", "因此", "可能", "需要",
        "机器人", "触摸事件", "日志证据", "源码证据", "安全规则", "前置检查",
        "current", "action", "event", "interaction", "module", "task", "rule", "trigger",
    }
    tokens = {
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_:-]{3,}|[\u4e00-\u9fff]{2,}", claim)
        if token.casefold() not in stop_words
    }
    refs: List[str] = []
    for log in logs:
        text = _log_search_text(log).casefold()
        if tokens and sum(token in text for token in tokens) >= 1:
            refs.append(_log_ref_for_claim(log))
    for source in sources:
        text = " ".join(str(source.get(key) or "") for key in ("repo", "file_path", "function_name", "matched_text", "snippet")).casefold()
        if tokens and sum(token in text for token in tokens) >= min(2, len(tokens)):
            refs.append(_source_ref_for_claim(source))
    return list(dict.fromkeys(refs))[:10]


def _log_ref_for_claim(log: Dict[str, Any]) -> str:
    return f"log:{log.get('module_name', '')}/{log.get('file_name', '')}:{int(log.get('line_no') or 0)}"


def _source_ref_for_claim(source: Dict[str, Any]) -> str:
    function = str(source.get("function_name") or "unknown")
    return f"source:{source.get('repo', '')}/{source.get('file_path', '')}:{function}"


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
    if "source_sync" in result:
        payload["source_sync"] = dict(result.get("source_sync") or {})
    if "source_index" in result:
        payload["source_index"] = dict(result.get("source_index") or {})
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
    if state.get("source_investigation"):
        request["source_investigation"] = dict(state.get("source_investigation") or {})
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
        "execution_chain": [],
        "evidence_logs": [],
        "evidence_sources": [],
        "evidence_claims": [],
        "recommended_actions": ["确认 Bug 发生时间、机器人类型和日志包是否完整。"],
        "confidence": 0.15,
        "questions_for_human": [
            "飞书工单中的发生时间是否准确？",
            "日志包是否包含主模块及其关联模块的完整时间窗口日志？",
        ],
        "agent_version": AGENT_VERSION,
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


def _analysis_modules(bug: Dict[str, Any], logs: List[Dict[str, Any]]) -> List[str]:
    """Select source repositories from the observed modules, not one hard-coded module."""
    result: List[str] = []
    primary = str(bug.get("main_module") or "").strip()
    if primary:
        result.append(primary)
    for log in logs:
        module = str(log.get("module_name") or "").strip()
        if module and module not in result:
            result.append(module)
    return result or ["unknown"]


def _next_source_followup(state: DiagnosisState) -> Dict[str, Any] | None:
    investigation = state.get("source_investigation") or {}
    if investigation.get("stop"):
        return None
    attempted = {
        (module.casefold(), query.casefold())
        for module, query in _attempted_source_queries(state)
    }
    for item in investigation.get("queries") or []:
        module = str(item.get("module_name") or "").strip()
        query = str(item.get("query") or "").strip()
        if module and query and (module.casefold(), query.casefold()) not in attempted:
            return dict(item)
    return None


def _attempted_source_queries(state: DiagnosisState) -> List[tuple[str, str]]:
    attempted: List[tuple[str, str]] = []
    for observation in state.get("observations") or []:
        if observation.get("tool_name") != "source_search":
            continue
        args = observation.get("args") or {}
        module = str(args.get("module_name") or "").strip()
        for value in args.get("keywords") or []:
            query = str(value).strip()
            if module and query and (module, query) not in attempted:
                attempted.append((module, query))
    return attempted


def _latest_source_module(state: DiagnosisState) -> str:
    for observation in reversed(state.get("observations") or []):
        if observation.get("tool_name") != "source_search" or not observation.get("ok"):
            continue
        if not (observation.get("result") or {}).get("sources"):
            continue
        return str((observation.get("args") or {}).get("module_name") or "").strip()
    return ""


def _allowed_source_followup_modules(
    state: DiagnosisState,
    current_module: str,
    additional_relations: List[Dict[str, Any]],
) -> List[str]:
    result = [current_module] if current_module else []
    relations = list(state.get("module_relations") or []) + additional_relations
    for relation in relations:
        if str(relation.get("from_module") or "") != current_module:
            continue
        target = str(relation.get("to_module") or "").strip()
        if target and target not in result:
            result.append(target)
    return result


def _registered_source_relations(
    state: DiagnosisState,
    current_module: str,
    sources: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not current_module or not sources:
        return []
    repositories = load_repositories(load_settings().source_repository_file)
    existing = {
        (
            str(relation.get("from_module") or ""),
            str(relation.get("to_module") or ""),
        )
        for relation in state.get("module_relations") or []
    }
    relations: List[Dict[str, Any]] = []
    for target in repositories:
        if target == current_module or (current_module, target) in existing:
            continue
        matched = [
            source
            for source in sources
            if _mentions_module(_source_search_text(source), target)
        ]
        refs = [str(source.get("file_path") or "") for source in matched if source.get("file_path")]
        if not refs:
            continue
        relations.append(
            {
                "from_module": current_module,
                "to_module": target,
                "reason": f"{current_module} 源码上下文引用已注册模块 {target}",
                "evidence_type": "source",
                "evidence_refs": list(dict.fromkeys(refs))[:10],
            }
        )
    return _unique_relations(relations)


def _next_source_modules(state: DiagnosisState) -> List[str]:
    modules = _analysis_modules(state.get("bug", {}), state.get("log_evidence") or [])
    attempted = {
        str(observation.get("args", {}).get("module_name") or "")
        for observation in state.get("observations") or []
        if observation.get("tool_name") == "source_search"
    }
    primary = modules[0]
    if primary not in attempted:
        return [primary]
    related = {
        str(relation.get("to_module") or "")
        for relation in state.get("module_relations") or []
        if str(relation.get("from_module") or "") == primary
    }
    return [module for module in modules[1:] if module in related and module not in attempted]


def _derive_module_relations(
    state: DiagnosisState,
    additional_logs: List[Dict[str, Any]],
    additional_sources: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    modules = _analysis_modules(state.get("bug", {}), list(state.get("log_evidence") or []) + additional_logs)
    primary = modules[0]
    logs = list(state.get("log_evidence") or []) + additional_logs
    sources = list(state.get("source_evidence") or []) + additional_sources
    primary_logs = [
        log for log in logs if str(log.get("module_name") or "") == primary
    ]
    primary_sources = [
        source
        for source in sources
        if str(source.get("repo") or "") == primary
        or str(source.get("file_path") or "").startswith(primary + "/")
    ]
    relations: List[Dict[str, Any]] = []
    for module in modules[1:]:
        source_matches = [
            source
            for source in primary_sources
            if _mentions_module(_source_search_text(source), module)
        ]
        log_matches = [
            log
            for log in primary_logs
            if _mentions_module(_log_search_text(log), module)
        ]
        timeline = _nearest_module_log_relation(logs, primary, module)
        correlation = _shared_log_correlation(logs, primary, module)
        anomaly = _nearby_anomaly_relation(logs, primary, module)
        if source_matches:
            evidence_type = "source"
            refs = [str(source.get("file_path") or "") for source in source_matches]
            reason = f"{primary} 源码证据引用 {module} 模块"
        elif log_matches:
            evidence_type = "log"
            refs = [_log_ref(log) for log in log_matches]
            reason = f"{primary} 日志出现 {module} 关联标识"
        elif correlation:
            evidence_type = "log"
            refs = list(correlation["evidence_refs"])
            reason = (
                f"{primary} 与 {module} 日志共享关联标识 "
                f"{correlation['correlation_key']}"
            )
            timeline = correlation
        elif anomaly:
            evidence_type = "log"
            refs = list(anomaly["evidence_refs"])
            reason = f"{module} 在主模块异常附近出现同时间窗口异常"
            timeline = anomaly
        else:
            continue
        relations.append(
            {
                "from_module": primary,
                "to_module": module,
                "reason": reason,
                "evidence_type": evidence_type,
                "evidence_refs": list(dict.fromkeys(refs))[:10],
                **timeline,
            }
        )
    return _unique_relations(relations)


def _nearest_module_log_relation(
    logs: List[Dict[str, Any]],
    primary: str,
    target: str,
) -> Dict[str, Any]:
    primary_logs = [
        log
        for log in logs
        if str(log.get("module_name") or "") == primary
        and _mentions_module(_log_search_text(log), target)
    ]
    target_logs = [log for log in logs if str(log.get("module_name") or "") == target]
    candidates = [
        (abs(int(target_log.get("log_time") or 0) - int(primary_log.get("log_time") or 0)), primary_log, target_log)
        for primary_log in primary_logs
        for target_log in target_logs
        if int(primary_log.get("log_time") or 0) > 0 and int(target_log.get("log_time") or 0) > 0
    ]
    if not candidates:
        return {}
    _, primary_log, target_log = min(candidates, key=lambda item: item[0])
    return {
        "time_delta_ms": int(target_log.get("log_time") or 0) - int(primary_log.get("log_time") or 0),
        "source_log_ref": _log_ref(primary_log),
        "target_log_ref": _log_ref(target_log),
    }


def _shared_log_correlation(
    logs: List[Dict[str, Any]],
    primary: str,
    target: str,
) -> Dict[str, Any]:
    primary_logs = [log for log in logs if str(log.get("module_name") or "") == primary]
    target_logs = [log for log in logs if str(log.get("module_name") or "") == target]
    candidates = []
    for primary_log in primary_logs:
        primary_values = _correlation_values(primary_log)
        if not primary_values:
            continue
        for target_log in target_logs:
            shared = primary_values & _correlation_values(target_log)
            if not shared:
                continue
            delta = _time_distance(primary_log, target_log)
            if delta != 2**63 - 1 and delta > 60_000:
                continue
            candidates.append((delta, sorted(shared)[0], primary_log, target_log))
    if not candidates:
        return {}
    _, key, primary_log, target_log = min(candidates, key=lambda item: item[0])
    return {
        "correlation_key": key,
        "evidence_refs": [_log_ref(primary_log), _log_ref(target_log)],
        "time_delta_ms": int(target_log.get("log_time") or 0) - int(primary_log.get("log_time") or 0),
        "source_log_ref": _log_ref(primary_log),
        "target_log_ref": _log_ref(target_log),
    }


def _nearby_anomaly_relation(
    logs: List[Dict[str, Any]],
    primary: str,
    target: str,
    *,
    max_delta_ms: int = 5000,
) -> Dict[str, Any]:
    abnormal_levels = {"warn", "warning", "error", "fatal"}
    primary_logs = [
        log
        for log in logs
        if str(log.get("module_name") or "") == primary
        and str(log.get("log_level") or "").casefold() in abnormal_levels
    ]
    target_logs = [
        log
        for log in logs
        if str(log.get("module_name") or "") == target
        and str(log.get("log_level") or "").casefold() in abnormal_levels
    ]
    candidates = [
        (_time_distance(primary_log, target_log), primary_log, target_log)
        for primary_log in primary_logs
        for target_log in target_logs
        if int(primary_log.get("log_time") or 0) > 0
        and int(target_log.get("log_time") or 0) > 0
    ]
    if not candidates:
        return {}
    delta, primary_log, target_log = min(candidates, key=lambda item: item[0])
    if delta > max_delta_ms:
        return {}
    return {
        "evidence_refs": [_log_ref(primary_log), _log_ref(target_log)],
        "time_delta_ms": int(target_log.get("log_time") or 0) - int(primary_log.get("log_time") or 0),
        "source_log_ref": _log_ref(primary_log),
        "target_log_ref": _log_ref(target_log),
    }


def _correlation_values(log: Dict[str, Any]) -> set[str]:
    text = _log_search_text(log)
    values: set[str] = set()
    key_pattern = re.compile(
        r"\b([A-Za-z_][\w.-]{0,63})\s*[:=]\s*"
        r"([A-Za-z0-9_.:/-]{3,})",
    )
    for match in key_pattern.finditer(text):
        if not _is_correlation_key(match.group(1)):
            continue
        value = match.group(2).strip(" ,;")
        if value.casefold() not in {"none", "null", "true", "false", "unknown"}:
            values.add(f"{match.group(1).casefold()}={value.casefold()}")
            values.add(value.casefold())
    for uuid in re.findall(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}\b", text):
        values.add(uuid.casefold())
    return values


def _time_distance(first: Dict[str, Any], second: Dict[str, Any]) -> int:
    first_time = int(first.get("log_time") or 0)
    second_time = int(second.get("log_time") or 0)
    if not first_time or not second_time:
        return 2**63 - 1
    return abs(second_time - first_time)


def _log_ref(log: Dict[str, Any]) -> str:
    return f"{log.get('file_name', '')}:{log.get('line_no', 0)}"


def _source_search_text(source: Dict[str, Any]) -> str:
    return " ".join(
        str(source.get(key) or "")
        for key in ("file_path", "function_name", "matched_text", "snippet")
    )


def _mentions_module(text: str, module: str) -> bool:
    searchable = _identifier_words(text)
    module_words = _identifier_words(module)
    if not searchable or not module_words:
        return False
    padded = f" {searchable} "
    if f" {module_words} " in padded:
        return True
    compact_module = module_words.replace(" ", "")
    return compact_module in set(searchable.split())


def _identifier_words(value: str) -> str:
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", value)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return re.sub(r"[^A-Za-z0-9]+", " ", text).strip().casefold()


def _is_correlation_key(value: str) -> bool:
    words = _identifier_words(value).split()
    if not words:
        return False
    if words[-1] in {"id", "uuid", "token", "seq", "sequence"}:
        return True
    compact = "".join(words)
    prefixes = {
        "trace",
        "span",
        "request",
        "req",
        "task",
        "action",
        "session",
        "transaction",
        "command",
        "cmd",
    }
    return any(compact == f"{prefix}id" for prefix in prefixes)


def _unique_relations(relations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    positions: Dict[tuple[str, str], int] = {}
    for relation in relations:
        from_module = str(relation.get("from_module") or "").strip()
        to_module = str(relation.get("to_module") or "").strip()
        evidence_refs = [
            str(value).strip()
            for value in relation.get("evidence_refs") or []
            if str(value).strip()
        ]
        if not from_module or not to_module or not evidence_refs:
            continue
        key = (
            from_module,
            to_module,
        )
        current = dict(relation)
        current["from_module"] = from_module
        current["to_module"] = to_module
        current["evidence_refs"] = evidence_refs[:10]
        if key not in positions:
            positions[key] = len(result)
            result.append(current)
            continue
        index = positions[key]
        existing = result[index]
        # A source relation is stronger than a log-only hint. Keep the richer
        # record while preserving timeline fields discovered in either pass.
        if existing.get("evidence_type") != "source" and current.get("evidence_type") == "source":
            existing, current = current, existing
        for field in ("time_delta_ms", "source_log_ref", "target_log_ref"):
            if field not in existing and field in current:
                existing[field] = current[field]
        existing["evidence_refs"] = list(dict.fromkeys(
            list(existing.get("evidence_refs") or []) + list(current.get("evidence_refs") or [])
        ))[:10]
        result[index] = existing
    return result


def _log_search_text(log: Dict[str, Any]) -> str:
    return " ".join(
        str(log.get(key) or "")
        for key in ("module_name", "file_name", "log_level", "message", "raw_line")
    )


def _unique_logs(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen = set()
    for log in logs:
        key = _log_key(log)
        if key in seen:
            continue
        result.append(dict(log))
        seen.add(key)
    return result


def _unique_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen = set()
    for source in sources:
        key = _source_key(source)
        if key in seen:
            continue
        result.append(dict(source))
        seen.add(key)
    return result


def _log_key(log: Dict[str, Any]) -> tuple[str, str, int, str]:
    return (
        str(log.get("module_name", "")),
        str(log.get("file_name", "")),
        int(log.get("line_no") or 0),
        str(log.get("raw_line") or log.get("message") or ""),
    )


def _source_key(source: Dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(source.get("repo", "")),
        str(source.get("file_path", "")),
        str(source.get("function_name") or source.get("snippet") or ""),
    )


def _knowledge_items(values: List[Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for value in values:
        if isinstance(value, dict):
            result.append(dict(value))
        else:
            result.append({"content": str(value)})
    return result


def _source_generation_detail(state: DiagnosisState) -> str:
    investigation = state.get("source_investigation") or {}
    mode = str(investigation.get("planning_mode") or "not_run")
    rounds = int(state.get("source_analysis_iteration") or 0)
    stop = bool(investigation.get("stop"))
    index_statuses = [
        dict((observation.get("result") or {}).get("source_index") or {})
        for observation in state.get("observations") or []
        if observation.get("tool_name") == "source_search"
        and (observation.get("result") or {}).get("source_index")
    ]
    strategies = list(
        dict.fromkeys(
            str(status.get("search_strategy") or "")
            for status in index_statuses
            if status.get("search_strategy")
        )
    )
    refresh_actions = list(
        dict.fromkeys(
            str(status.get("action") or "")
            for status in index_statuses
            if status.get("action")
        )
    )
    strategy = "+".join(strategies) or "not_run"
    refresh = "+".join(refresh_actions) or "not_run"
    return (
        f"source planning={mode}, rounds={rounds}, stop={str(stop).lower()}; "
        f"source index={strategy}, refresh={refresh}"
    )


def _public_trace(events: List[GraphTraceEvent]) -> List[Dict[str, str]]:
    """Expose operational trace fields without model prompts or hidden reasoning."""
    result: List[Dict[str, str]] = []
    for event in events:
        node = str(event.get("node") or "").strip()
        status = str(event.get("event") or "").strip()
        detail = str(event.get("detail") or "").strip()
        if not node or not status:
            continue
        result.append({"node": node, "event": status, "detail": detail[:280]})
    return result


def _trace(node: str, event: str, detail: str) -> GraphTraceEvent:
    return {"node": node, "event": event, "detail": detail}
