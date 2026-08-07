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
    logs = _compact_items(request.get("logs", []), limit=30, max_text_len=1200)
    sources = _compact_items(request.get("sources", []), limit=12, max_text_len=6000)
    history_cases = _compact_items(request.get("history_cases", []), limit=10, max_text_len=1200)
    knowledge = _compact_items(request.get("knowledge", []), limit=20, max_text_len=1600)
    source_investigation = request.get("source_investigation", {})
    report_schema = json.dumps(DiagnosisReport.model_json_schema(), ensure_ascii=False)
    return (
        "你是 RobotOps AI 的机器人研发 Bug 诊断 Agent。\n"
        "你必须只输出一个符合 DiagnosisReport schema 的 JSON 对象，不要输出 Markdown。\n"
        "只允许基于输入的 Bug、日志证据、源码证据、历史案例、知识库和规则 baseline 生成报告。\n"
        "源码 snippet 是由本次日志动态检索得到的函数级或文件级上下文；必须阅读控制流上下文，"
        "不能只根据命中单行或函数名下结论。\n"
        "如果源码或日志显示跨模块调用，只能在关联模块证据支持时确认执行结果；"
        "调用语句本身只能证明调用意图。\n"
        "module_relations 每项只能使用 from_module、to_module、reason、evidence_type、"
        "evidence_refs、time_delta_ms、source_log_ref、target_log_ref 字段；"
        "没有 evidence_refs 时不要输出该关系。\n"
        "evidence_claims 必须把 summary 和 possible_causes 拆成可复核结论；每项只能引用输入中真实存在的日志/源码证据，"
        "引用格式使用 log:module/file:line 或 source:repo/file:function；没有证据时 support_level=unknown、evidence_refs=[]。\n"
        "规则 baseline 只是补充先验，不得覆盖与本次真实日志、源码上下文冲突的证据。\n"
        "Source investigation 仅记录检索过程和停止原因，不是独立事实证据。\n"
        "trace_id 和 diagnostic_trace 由服务端生成，不需要你填写，也不要输出隐藏推理。\n"
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
        f"Source investigation: {source_investigation}\n"
        f"Rule baseline: {rule_report}\n"
    )


def _compact_items(values: List[Any], *, limit: int, max_text_len: int = 800) -> List[Any]:
    compacted: List[Any] = []
    for value in list(values)[:limit]:
        if isinstance(value, dict):
            compacted.append(
                {
                    key: _trim_text(item, max_len=max_text_len)
                    for key, item in value.items()
                }
            )
        else:
            compacted.append(_trim_text(value, max_len=max_text_len))
    return compacted


def _trim_text(value: Any, *, max_len: int = 800) -> Any:
    if not isinstance(value, str):
        return value
    return value if len(value) <= max_len else value[:max_len] + "...[truncated]"
