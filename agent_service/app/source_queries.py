from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple


_LEVEL_PRIORITY = {
    "fatal": 0,
    "error": 1,
    "warn": 2,
    "warning": 2,
    "info": 3,
    "debug": 4,
    "trace": 5,
}
_COMMON_IDENTIFIERS = {
    "debug",
    "error",
    "false",
    "fatal",
    "info",
    "null",
    "trace",
    "true",
    "warn",
    "warning",
}
_DYNAMIC_TOKEN_RE = re.compile(
    r"(?<![\w])(?:"
    r"0x[0-9a-fA-F]+"
    r"|[+-]?\d+(?:\.\d+)?"
    r"|[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}"
    r"|(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?"
    r")(?![\w])"
)
_FIELD_ONLY_RE = re.compile(r"^[A-Za-z_][\w.-]{0,31}\s*[:=]\s*\S+(?:\s+\S+){0,2}$")
_LOG_PREFIX_RE = re.compile(
    r"^\s*(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}[T ]\d{1,2}:\d{2}:\d{2}(?:[.,]\d+)?\s+)?"
    r"(?:TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL)\b[\s:|\]-]*",
    re.IGNORECASE,
)


def build_source_queries(
    *,
    bug: Dict[str, Any],
    logs: Iterable[Dict[str, Any]],
    module_name: str,
    max_queries: int = 8,
) -> List[str]:
    """Derive source-search text from this Bug's evidence without rule/path hints."""
    ranked: List[Tuple[int, int, str]] = []
    order = 0
    occurred_time = _int_value(bug.get("occurred_time"))
    normalized_module = module_name.casefold()
    module_logs = [
        log
        for log in logs
        if str(log.get("module_name") or "").strip().casefold() == normalized_module
    ]
    module_logs.sort(key=lambda log: _log_sort_key(log, occurred_time))

    for log in module_logs[:24]:
        message = _log_message(log)
        if not message:
            continue
        for priority, query in _queries_from_text(message):
            ranked.append((priority, order, query))
            order += 1

    for field in ("title", "description"):
        value = str(bug.get(field) or "").strip()
        if not value:
            continue
        for priority, query in _queries_from_text(value):
            ranked.append((priority + 50, order, query))
            order += 1

    result: List[str] = []
    seen: set[str] = set()
    for _, _, query in sorted(ranked, key=lambda item: (item[0], item[1])):
        normalized = _normalize_query(query)
        key = normalized.casefold()
        if not _is_useful_query(normalized) or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
        if len(result) >= max(1, max_queries):
            break
    return result


def _queries_from_text(value: str) -> List[Tuple[int, str]]:
    text = _clean_text(value)
    if not text:
        return []

    candidates: List[Tuple[int, str]] = []
    candidates.extend(_code_identifiers(text))

    clauses = [item.strip(" \t\r\n\"'[]()") for item in re.split(r"[,，;；|]", text)]
    for clause in clauses:
        clause = _normalize_query(clause)
        if not _is_useful_query(clause) or _FIELD_ONLY_RE.fullmatch(clause):
            continue

        has_dynamic_value = bool(_DYNAMIC_TOKEN_RE.search(clause))
        scrubbed = _normalize_query(_DYNAMIC_TOKEN_RE.sub(" ", clause))
        if _is_useful_query(scrubbed):
            candidates.append((3 if not has_dynamic_value else 4, scrubbed))

        field_prefix = re.match(r"^(.{4,60}?)(?:\s*[:=]\s*)\S+", clause)
        if field_prefix and _is_useful_query(field_prefix.group(1)):
            candidates.append((4, field_prefix.group(1)))

        words = re.findall(r"[A-Za-z_][A-Za-z0-9_./:-]*|[\u4e00-\u9fff]+", scrubbed)
        if len(words) >= 4:
            for size in range(3, min(5, len(words)) + 1):
                candidates.append((20 + size, " ".join(words[:size])))
            candidates.append((28, " ".join(words[-min(4, len(words)) :])))

    if len(text) <= 120 and not _DYNAMIC_TOKEN_RE.search(text) and _is_useful_query(text):
        candidates.append((35, text))
    return candidates


def _code_identifiers(text: str) -> List[Tuple[int, str]]:
    patterns = (
        (5, r"\b[A-Za-z_]\w*(?:::[A-Za-z_]\w*)+\b"),
        (6, r"\b[A-Za-z_]\w{2,}\s*(?=\()"),
        (8, r"\b[A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]*)+\b"),
        (8, r"/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+"),
        (30, r"\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+\b"),
        (32, r"\b[A-Z][A-Z0-9_]{3,}\b"),
    )
    result: List[Tuple[int, str]] = []
    seen: set[str] = set()
    for priority, pattern in patterns:
        for match in re.finditer(pattern, text):
            value = match.group(0).strip()
            key = value.casefold()
            if key in _COMMON_IDENTIFIERS or key in seen:
                continue
            seen.add(key)
            result.append((priority, value))
    return result


def _clean_text(value: str) -> str:
    text = re.sub(r"\x1b\[[0-9;]*m", "", value)
    return _LOG_PREFIX_RE.sub("", text).strip()


def _normalize_query(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \t\r\n\"'[](),;|")


def _is_useful_query(value: str) -> bool:
    if len(value) < 4 or len(value) > 160:
        return False
    if value.casefold() in _COMMON_IDENTIFIERS:
        return False
    return any(character.isalpha() or "\u4e00" <= character <= "\u9fff" for character in value)


def _log_message(log: Dict[str, Any]) -> str:
    return str(log.get("message") or log.get("raw_line") or "").strip()


def _log_sort_key(log: Dict[str, Any], occurred_time: int) -> Tuple[int, int, int]:
    level = str(log.get("log_level") or "").casefold()
    level_priority = _LEVEL_PRIORITY.get(level, 6)
    log_time = _int_value(log.get("log_time"))
    distance = abs(log_time - occurred_time) if log_time and occurred_time else 0
    return level_priority, distance, _int_value(log.get("line_no"))


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
