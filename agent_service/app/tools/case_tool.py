from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


def search_cases(roots: Sequence[str], args: Dict[str, Any]) -> Dict[str, Any]:
    """Search a small local case index without making the agent depend on a DB."""
    query = _query_text(args)
    robot_type = str(args.get("robot_type") or "").strip().lower()
    main_module = str(args.get("main_module") or "").strip().lower()
    limit = max(1, min(int(args.get("max_results") or 5), 20))
    matches: List[Dict[str, Any]] = []
    for case in _load_cases(roots):
        score = _score_case(case, query, robot_type, main_module)
        if score <= 0:
            continue
        item = dict(case)
        item["match_score"] = round(score, 3)
        matches.append(item)
    matches.sort(key=lambda item: float(item.get("match_score") or 0), reverse=True)
    return {"ok": True, "history_cases": matches[:limit]}


def _load_cases(roots: Sequence[str]) -> Iterable[Dict[str, Any]]:
    for root_value in roots:
        root = Path(root_value).expanduser()
        if not root.exists():
            continue
        paths = [root] if root.is_file() else sorted(root.rglob("*.json")) + sorted(root.rglob("*.jsonl"))
        for path in paths:
            try:
                if path.suffix.lower() == ".jsonl":
                    values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
                else:
                    value = json.loads(path.read_text(encoding="utf-8"))
                    values = value.get("cases", []) if isinstance(value, dict) else value
                if isinstance(values, dict):
                    values = [values]
                for case in values:
                    if isinstance(case, dict):
                        yield case
            except (OSError, UnicodeError, ValueError, TypeError):
                continue


def _query_text(args: Dict[str, Any]) -> str:
    values = [args.get("title", ""), args.get("description", ""), " ".join(str(item) for item in args.get("keywords") or [])]
    return " ".join(str(value) for value in values if value).strip().lower()


def _score_case(case: Dict[str, Any], query: str, robot_type: str, main_module: str) -> float:
    searchable = " ".join(_flatten_text(case)).lower()
    if not searchable:
        return 0.0
    tokens = _tokens(query)
    matched = sum(1 for token in tokens if token in searchable)
    score = matched / max(len(tokens), 1)
    if robot_type and robot_type == str(case.get("robot_type") or "").lower():
        score += 0.25
    if main_module and main_module == str(case.get("main_module") or case.get("module") or "").lower():
        score += 0.25
    return score


def _flatten_text(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for child in value.values():
            yield from _flatten_text(child)
    elif isinstance(value, list):
        for child in value:
            yield from _flatten_text(child)
    elif value is not None:
        yield str(value)


def _tokens(value: str) -> List[str]:
    words = [item for item in re.split(r"[^a-zA-Z0-9_\u4e00-\u9fff]+", value) if item]
    result: List[str] = []
    for word in words:
        if len(word) > 1 and any("\u4e00" <= char <= "\u9fff" for char in word):
            result.extend(word[index : index + 2] for index in range(len(word) - 1))
        else:
            result.append(word)
    return list(dict.fromkeys(result))
