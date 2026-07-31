from __future__ import annotations

import json
from typing import Any, Dict, List

from agent_service.app.models import DiagnosisReport

try:
    from langchain_deepseek import ChatDeepSeek
except ImportError:  # pragma: no cover - optional until a live DeepSeek call is enabled.
    ChatDeepSeek = None


class DeepSeekUnavailable(RuntimeError):
    pass


def generate_structured_report(
    *,
    model: str,
    request: Dict[str, Any],
    rule_report: Dict[str, Any],
) -> Dict[str, Any]:
    if ChatDeepSeek is None:
        raise DeepSeekUnavailable("langchain-deepseek is not installed")

    try:
        llm = ChatDeepSeek(model=model, temperature=0, max_retries=2)
        # DeepSeek thinking models reject tool_choice, so schema validation must use JSON mode.
        structured_llm = llm.with_structured_output(DiagnosisReport, method="json_mode")
        prompt = _build_prompt(request, rule_report)
        response = structured_llm.invoke(prompt)
        if isinstance(response, DiagnosisReport):
            return response.model_dump()
        if isinstance(response, dict):
            return DiagnosisReport(**response).model_dump()
    except Exception as exc:
        raise DeepSeekUnavailable(f"DeepSeek structured report failed: {exc}") from exc
    raise DeepSeekUnavailable("DeepSeek returned an unsupported structured output type")


def _build_prompt(request: Dict[str, Any], rule_report: Dict[str, Any]) -> str:
    bug = request.get("bug", {})
    logs = _compact_items(request.get("logs", []), limit=30)
    sources = _compact_items(request.get("sources", []), limit=20)
    history_cases = _compact_items(request.get("history_cases", []), limit=10)
    knowledge = _compact_items(request.get("knowledge", []), limit=20)
    report_schema = json.dumps(DiagnosisReport.model_json_schema(), ensure_ascii=False)
    return (
        "你是 RobotOps AI 的机器人研发 Bug 诊断 Agent。\n"
        "你必须只输出一个符合 DiagnosisReport schema 的 JSON 对象，不要输出 Markdown。\n"
        "只允许基于输入的 Bug、日志证据、源码证据、历史案例、知识库和规则 baseline 生成报告。\n"
        "execution_chain 只能描述规则 baseline 或证据支持的执行阶段，不能把未观测到的阶段写成确定事实。\n"
        "不能编造日志行、源码路径、函数名、故障码或责任模块。\n"
        "如果日志证据不足，confidence 必须 <= 0.35，并在 questions_for_human 中要求补充日志。\n"
        "如果只有日志证据、没有源码证据，confidence 必须 <= 0.85。\n"
        "如果规则 baseline 已经给出明确证据，最终报告必须保留这些证据或给出更低置信度。\n\n"
        f"DiagnosisReport JSON schema: {report_schema}\n"
        f"Bug: {bug}\n"
        f"Logs: {logs}\n"
        f"Sources: {sources}\n"
        f"History cases: {history_cases}\n"
        f"Knowledge: {knowledge}\n"
        f"Rule baseline: {rule_report}\n"
    )


def _compact_items(values: List[Any], *, limit: int) -> List[Any]:
    compacted: List[Any] = []
    for value in list(values)[:limit]:
        if isinstance(value, dict):
            compacted.append({key: _trim_text(item) for key, item in value.items()})
        else:
            compacted.append(_trim_text(value))
    return compacted


def _trim_text(value: Any, *, max_len: int = 800) -> Any:
    if not isinstance(value, str):
        return value
    return value if len(value) <= max_len else value[:max_len] + "...[truncated]"
