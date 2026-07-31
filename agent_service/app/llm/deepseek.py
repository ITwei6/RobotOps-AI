from __future__ import annotations

from typing import Any, Dict

from agent_service.app.models import DiagnosisReport


class DeepSeekUnavailable(RuntimeError):
    pass


def generate_structured_report(
    *,
    model: str,
    request: Dict[str, Any],
    rule_report: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        from langchain_deepseek import ChatDeepSeek
    except ImportError as exc:
        raise DeepSeekUnavailable("langchain-deepseek is not installed") from exc

    llm = ChatDeepSeek(model=model, temperature=0, max_retries=2)
    structured_llm = llm.with_structured_output(DiagnosisReport)
    prompt = _build_prompt(request, rule_report)
    response = structured_llm.invoke(prompt)
    if isinstance(response, DiagnosisReport):
        return response.model_dump()
    if isinstance(response, dict):
        return DiagnosisReport(**response).model_dump()
    raise DeepSeekUnavailable("DeepSeek returned an unsupported structured output type")


def _build_prompt(request: Dict[str, Any], rule_report: Dict[str, Any]) -> str:
    bug = request.get("bug", {})
    logs = request.get("logs", [])
    sources = request.get("sources", [])
    history_cases = request.get("history_cases", [])
    knowledge = request.get("knowledge", [])
    return (
        "你是 RobotOps AI 的机器人研发 Bug 诊断 Agent。"
        "只能基于输入的日志证据、源码证据、历史案例、知识库和规则 baseline 生成报告；"
        "证据不足时必须降低 confidence，并提出 questions_for_human。\n\n"
        f"Bug: {bug}\n"
        f"Logs: {logs[:30]}\n"
        f"Sources: {sources[:20]}\n"
        f"History cases: {history_cases[:10]}\n"
        f"Knowledge: {knowledge[:20]}\n"
        f"Rule baseline: {rule_report}\n"
    )
