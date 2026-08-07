from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List


def load_evaluation_cases(path: str | Path) -> List[Dict[str, Any]]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = value.get("cases", value) if isinstance(value, dict) else value
    if not isinstance(cases, list):
        raise ValueError("evaluation cases must be a list")
    return [dict(case) for case in cases if isinstance(case, dict)]


def evaluate_cases(
    cases: Iterable[Dict[str, Any]],
    *,
    runner: Callable[[Dict[str, Any]], Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    if runner is None:
        from agent_service.app.workflow import run_diagnosis_workflow

        runner = run_diagnosis_workflow

    results: List[Dict[str, Any]] = []
    for case in cases:
        case_id = str(case.get("case_id") or "unknown")
        request = dict(case.get("request") or {})
        expected = dict(case.get("expected") or {})
        report = runner(request)
        evidence_sources = list(report.get("evidence_sources") or [])
        source_text = "\n".join(
            " ".join(
                str(source.get(field) or "")
                for field in ("repo", "file_path", "function_name", "matched_text", "snippet")
            )
            for source in evidence_sources
        ).casefold()
        required_sources = [str(value) for value in expected.get("required_source_functions") or []]
        source_hits = [value for value in required_sources if value.casefold() in source_text]
        module_match = (
            not expected.get("suspected_module")
            or str(report.get("suspected_module") or "").casefold()
            == str(expected.get("suspected_module") or "").casefold()
        )
        source_match = len(source_hits) == len(required_sources)
        grounded = all(
            bool(str(source.get("file_path") or "").strip())
            and bool(str(source.get("function_name") or "").strip())
            for source in evidence_sources
        )
        trace_nodes = {
            str(item.get("node") or "")
            for item in report.get("diagnostic_trace") or []
        }
        trace_complete = {"normalize_input", "finalize"}.issubset(trace_nodes)
        valid_refs = {
            f"log:{item.get('module_name', '')}/{item.get('file_name', '')}:{int(item.get('line_no') or 0)}"
            for item in report.get("evidence_logs") or []
        } | {
            f"source:{item.get('repo', '')}/{item.get('file_path', '')}:{item.get('function_name') or 'unknown'}"
            for item in evidence_sources
        }
        claims = list(report.get("evidence_claims") or [])
        claim_grounded = all(
            all(str(ref) in valid_refs for ref in claim.get("evidence_refs") or [])
            for claim in claims
        )
        claim_coverage = _rate(sum(bool(claim.get("evidence_refs")) for claim in claims), len(claims)) if claims else 0.0
        results.append(
            {
                "case_id": case_id,
                "passed": module_match and source_match,
                "suspected_module": report.get("suspected_module", ""),
                "module_match": module_match,
                "required_source_functions": required_sources,
                "source_hits": source_hits,
                "source_match": source_match,
                "evidence_grounded": grounded,
                "trace_complete": trace_complete,
                "confidence": float(report.get("confidence") or 0.0),
                "generation_mode": report.get("generation_mode", ""),
                "trace_id_present": bool(str(report.get("trace_id") or "")),
                "claim_grounded": claim_grounded,
                "claim_evidence_coverage": claim_coverage,
            }
        )

    total = len(results)
    return {
        "total_cases": total,
        "passed_cases": sum(bool(item["passed"]) for item in results),
        "pass_rate": _rate(sum(bool(item["passed"]) for item in results), total),
        "suspected_module_accuracy": _rate(
            sum(bool(item["module_match"]) for item in results), total
        ),
        "required_source_hit_rate": _rate(
            sum(bool(item["source_match"]) for item in results), total
        ),
        "evidence_grounding_rate": _rate(
            sum(bool(item["evidence_grounded"]) for item in results), total
        ),
        "trace_completion_rate": _rate(
            sum(bool(item["trace_complete"]) for item in results), total
        ),
        "trace_id_rate": _rate(
            sum(bool(item["trace_id_present"]) for item in results), total
        ),
        "claim_grounding_rate": _rate(
            sum(bool(item["claim_grounded"]) for item in results), total
        ),
        "claim_evidence_coverage": round(
            sum(float(item["claim_evidence_coverage"]) for item in results) / total, 4
        ) if total else 0.0,
        "average_confidence": round(
            sum(float(item["confidence"]) for item in results) / total, 4
        ) if total else 0.0,
        "cases": results,
    }


def _rate(value: int, total: int) -> float:
    return round(value / total, 4) if total else 0.0
