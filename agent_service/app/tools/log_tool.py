from __future__ import annotations

import json
from typing import Any, Dict, List
from urllib import error, request


def fetch_log_context(*, log_service_url: str, timeout_seconds: float, args: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "bug_id": str(args.get("bug_id") or ""),
        "package_id": str(args.get("package_id") or args.get("log_package_id") or ""),
        "module_name": str(args.get("module_name") or ""),
        "center_time": _int_value(args.get("center_time") or args.get("occurred_time")),
        "before_ms": _seconds_to_ms(args.get("seconds_before"), default_ms=300_000),
        "after_ms": _seconds_to_ms(args.get("seconds_after"), default_ms=300_000),
        "limit": max(1, min(_int_value(args.get("limit"), 200), 500)),
    }
    endpoint = f"{log_service_url}/robotops.log.LogService/GetLogContext"
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        return {"ok": False, "logs": [], "error": f"log-service request failed: {exc}"}
    except json.JSONDecodeError as exc:
        return {"ok": False, "logs": [], "error": f"log-service returned invalid JSON: {exc}"}

    common = data.get("response") or {}
    if int(common.get("code") or 0) != 0:
        return {"ok": False, "logs": [], "error": str(common.get("message") or "log-service returned error")}

    logs = [_normalize_log(item) for item in data.get("logs") or []]
    keywords = [str(item).lower() for item in args.get("keywords") or [] if str(item).strip()]
    if keywords:
        matched = [item for item in logs if _matches_keywords(item, keywords)]
        if matched:
            logs = matched
    return {"ok": True, "logs": logs}


def _normalize_log(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "module_name": str(item.get("module_name") or ""),
        "file_name": str(item.get("file_name") or ""),
        "line_no": _int_value(item.get("line_no")),
        "log_time": _int_value(item.get("log_time")),
        "log_level": str(item.get("log_level") or ""),
        "message": str(item.get("message") or ""),
        "raw_line": str(item.get("raw_line") or item.get("message") or ""),
    }


def _matches_keywords(item: Dict[str, Any], keywords: List[str]) -> bool:
    text = f"{item.get('message', '')}\n{item.get('raw_line', '')}".lower()
    return any(keyword in text for keyword in keywords)


def _seconds_to_ms(value: Any, *, default_ms: int) -> int:
    if value is None or value == "":
        return default_ms
    return max(0, _int_value(value) * 1000)


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
