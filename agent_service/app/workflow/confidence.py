from __future__ import annotations

from typing import Any, Dict, List


def calibrate_report_confidence(
    report: Dict[str, Any],
    log_evidence: List[Dict[str, Any]],
    source_evidence: List[Dict[str, Any]],
    errors: List[str],
) -> Dict[str, Any]:
    updated = dict(report)
    confidence = float(updated.get("confidence") or 0.0)

    if not log_evidence:
        confidence = min(confidence, 0.35)
    elif not source_evidence:
        confidence = min(confidence, 0.85)

    if any("llm" in error.lower() or "deepseek" in error.lower() for error in errors):
        confidence = min(confidence, 0.75)

    updated["confidence"] = round(max(0.0, min(confidence, 0.92)), 2)

    if updated["confidence"] < 0.5:
        questions = list(updated.get("questions_for_human") or [])
        question = "请补充发生时间前后 interaction、mc、hds、sm、agent 多模块日志证据。"
        if question not in questions:
            questions.append(question)
        updated["questions_for_human"] = questions

    return updated
