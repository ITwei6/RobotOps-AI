from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from pydantic import BaseModel, Field

try:
    from langchain_deepseek import ChatDeepSeek
except ImportError:  # pragma: no cover - deterministic planning remains available.
    ChatDeepSeek = None


class SourcePlanningUnavailable(RuntimeError):
    pass


class SourceFollowupQuery(BaseModel):
    module_name: str
    query: str
    reason: str = ""
    evidence_ref: str = ""


class SourceInvestigationPlan(BaseModel):
    findings: List[str] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)
    queries: List[SourceFollowupQuery] = Field(default_factory=list)
    stop: bool = False
    stop_reason: str = ""


def generate_source_investigation(
    *,
    model: str,
    bug: Dict[str, Any],
    logs: Sequence[Dict[str, Any]],
    sources: Sequence[Dict[str, Any]],
    allowed_modules: Sequence[str],
    attempted_queries: Sequence[Tuple[str, str]],
) -> Dict[str, Any]:
    if ChatDeepSeek is None:
        raise SourcePlanningUnavailable("langchain-deepseek is not installed")

    try:
        llm = ChatDeepSeek(model=model, temperature=0, max_retries=2)
        structured_llm = llm.with_structured_output(SourceInvestigationPlan, method="json_mode")
        response = structured_llm.invoke(
            _build_prompt(
                bug=bug,
                logs=logs,
                sources=sources,
                allowed_modules=allowed_modules,
                attempted_queries=attempted_queries,
            )
        )
        if isinstance(response, SourceInvestigationPlan):
            return response.model_dump()
        if isinstance(response, dict):
            return SourceInvestigationPlan(**response).model_dump()
    except Exception as exc:
        raise SourcePlanningUnavailable(f"DeepSeek source planning failed: {exc}") from exc
    raise SourcePlanningUnavailable("DeepSeek returned an unsupported source plan")


def ground_source_investigation(
    plan: Dict[str, Any],
    *,
    sources: Sequence[Dict[str, Any]],
    allowed_modules: Sequence[str],
    attempted_queries: Iterable[Tuple[str, str]],
    max_queries: int = 3,
) -> Dict[str, Any]:
    parsed = SourceInvestigationPlan(**plan)
    allowed = {
        str(module).strip().casefold(): str(module).strip()
        for module in allowed_modules
        if str(module).strip()
    }
    attempted = {
        (str(module).strip().casefold(), str(query).strip().casefold())
        for module, query in attempted_queries
    }
    accepted: List[Dict[str, Any]] = []
    rejected = 0
    seen: set[Tuple[str, str]] = set()

    if not parsed.stop:
        for candidate in parsed.queries:
            module_key = candidate.module_name.strip().casefold()
            query = _normalize_query(candidate.query)
            key = (module_key, query.casefold())
            if (
                module_key not in allowed
                or not _valid_query(query)
                or key in attempted
                or key in seen
            ):
                rejected += 1
                continue
            evidence = _ground_query(query, candidate.evidence_ref, sources)
            if evidence is None:
                rejected += 1
                continue
            seen.add(key)
            accepted.append(
                {
                    "module_name": allowed[module_key],
                    "query": query,
                    "reason": candidate.reason.strip()[:300],
                    "evidence_ref": evidence,
                }
            )
            if len(accepted) >= max(1, max_queries):
                break

    return {
        "findings": [value.strip()[:500] for value in parsed.findings if value.strip()][:6],
        "unresolved_questions": [
            value.strip()[:500]
            for value in parsed.unresolved_questions
            if value.strip()
        ][:6],
        "queries": accepted,
        "stop": bool(parsed.stop),
        "stop_reason": parsed.stop_reason.strip()[:500],
        "rejected_query_count": rejected,
    }


def build_deterministic_source_investigation(
    *,
    sources: Sequence[Dict[str, Any]],
    module_name: str,
    allowed_modules: Sequence[str],
    attempted_queries: Iterable[Tuple[str, str]],
    max_queries: int = 3,
) -> Dict[str, Any]:
    candidates: List[Dict[str, str]] = []
    for source in sources:
        evidence_ref = _source_ref(source)
        for query in _source_symbols(source):
            candidates.append(
                {
                    "module_name": module_name,
                    "query": query,
                    "reason": "源码上下文中存在尚未检索的调用符号。",
                    "evidence_ref": evidence_ref,
                }
            )

    grounded = ground_source_investigation(
        {
            "queries": candidates,
            "stop": not candidates,
            "stop_reason": "未发现可继续检索的调用符号。" if not candidates else "",
        },
        sources=sources,
        allowed_modules=allowed_modules,
        attempted_queries=attempted_queries,
        max_queries=max_queries,
    )
    if candidates and not grounded["queries"]:
        grounded["stop"] = True
        grounded["stop_reason"] = "源码调用符号均已检索或未通过证据校验。"
    return grounded


def _build_prompt(
    *,
    bug: Dict[str, Any],
    logs: Sequence[Dict[str, Any]],
    sources: Sequence[Dict[str, Any]],
    allowed_modules: Sequence[str],
    attempted_queries: Sequence[Tuple[str, str]],
) -> str:
    schema = json.dumps(SourceInvestigationPlan.model_json_schema(), ensure_ascii=False)
    compact_logs = [
        {
            key: _trim(value, 1000)
            for key, value in log.items()
            if key in {"module_name", "file_name", "line_no", "log_time", "log_level", "message", "raw_line"}
        }
        for log in list(logs)[:20]
    ]
    compact_sources = [
        {
            "repo": source.get("repo", ""),
            "file_path": source.get("file_path", ""),
            "function_name": source.get("function_name", ""),
            "matched_text": source.get("matched_text", ""),
            "snippet": _trim(source.get("snippet", ""), 4000),
            "evidence_ref": _source_ref(source),
        }
        for source in list(sources)[:8]
    ]
    return (
        "你是 RobotOps AI 的源码调查规划节点，不负责生成最终诊断报告。\n"
        "你必须只输出符合 SourceInvestigationPlan schema 的 JSON 对象。\n"
        "阅读本次真实日志和源码函数上下文，判断是否还需要检索被调函数、类、RPC、Topic 或接口。\n"
        "query 必须逐字复制自 Sources 的 function_name、matched_text 或 snippet，禁止创造函数名、文件名和路径。\n"
        "module_name 只能从 Allowed modules 中选择；跨模块查询必须有当前源码中的调用或接口证据。\n"
        "evidence_ref 必须使用 Sources 中提供的 evidence_ref。\n"
        "不要重复 Attempted queries。最多输出 3 个查询，并按诊断价值排序。\n"
        "已有源码足以解释现象，或没有新的有证据查询时，设置 stop=true 并说明原因。\n\n"
        f"SourceInvestigationPlan JSON schema: {schema}\n"
        f"Bug: {json.dumps(bug, ensure_ascii=False)}\n"
        f"Allowed modules: {json.dumps(list(allowed_modules), ensure_ascii=False)}\n"
        f"Attempted queries: {json.dumps(list(attempted_queries), ensure_ascii=False)}\n"
        f"Logs: {json.dumps(compact_logs, ensure_ascii=False)}\n"
        f"Sources: {json.dumps(compact_sources, ensure_ascii=False)}\n"
    )


def _ground_query(
    query: str,
    evidence_ref: str,
    sources: Sequence[Dict[str, Any]],
) -> str | None:
    requested_ref = evidence_ref.strip().casefold()
    for source in sources:
        valid_refs = {
            str(source.get("file_path") or "").strip().casefold(),
            str(source.get("function_name") or "").strip().casefold(),
            _source_ref(source).casefold(),
        }
        if requested_ref and requested_ref not in valid_refs:
            continue
        if query.casefold() in _source_text(source).casefold():
            return _source_ref(source)
    return None


def _source_symbols(source: Dict[str, Any]) -> List[str]:
    text = str(source.get("snippet") or "")
    owner = str(source.get("function_name") or "")
    owner_names = {owner.casefold(), owner.rsplit("::", 1)[-1].casefold(), owner.rsplit(".", 1)[-1].casefold()}
    candidates: List[str] = []
    patterns = (
        r"\b[A-Za-z_]\w*(?:::[A-Za-z_]\w*)+\s*(?=\()",
        r"(?:->|\.)\s*([A-Za-z_]\w*)\s*(?=\()",
        r"(?<![:>.])\b([A-Za-z_]\w*)\s*(?=\()",
        r"/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            value = (match.group(1) if match.lastindex else match.group(0)).strip()
            if _skip_symbol(value, owner_names) or value in candidates:
                continue
            candidates.append(value)
    return candidates[:12]


def _skip_symbol(value: str, owner_names: set[str]) -> bool:
    name = value.rsplit("::", 1)[-1].casefold()
    if value.casefold() in owner_names or name in owner_names:
        return True
    if name in {
        "if",
        "for",
        "while",
        "switch",
        "catch",
        "return",
        "sizeof",
        "static_cast",
        "dynamic_cast",
        "reinterpret_cast",
        "const_cast",
        "getinstance",
    }:
        return True
    upper = value.upper()
    return upper == value and ("LOG" in upper or len(value) <= 3)


def _source_ref(source: Dict[str, Any]) -> str:
    path = str(source.get("file_path") or "").strip()
    function = str(source.get("function_name") or "").strip()
    return f"{path}:{function}" if function else path


def _source_text(source: Dict[str, Any]) -> str:
    return " ".join(
        str(source.get(key) or "")
        for key in ("file_path", "function_name", "matched_text", "snippet")
    )


def _normalize_query(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip(" \t\r\n\"'[](),;")


def _valid_query(value: str) -> bool:
    return 3 <= len(value) <= 160 and any(character.isalpha() for character in value)


def _trim(value: Any, max_len: int) -> Any:
    if not isinstance(value, str):
        return value
    return value if len(value) <= max_len else value[:max_len] + "...[truncated]"
