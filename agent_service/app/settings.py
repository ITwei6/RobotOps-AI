from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSettings:
    llm_enabled: bool
    deepseek_api_key: str
    llm_model: str
    max_tool_iterations: int
    log_service_url: str
    tool_timeout_seconds: float
    source_search_roots: tuple[str, ...]
    case_search_roots: tuple[str, ...]
    knowledge_search_roots: tuple[str, ...]


def load_settings() -> AgentSettings:
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    llm_flag = os.getenv("ROBOTOPS_LLM_ENABLED", "true").strip().lower()
    max_tool_iterations = _int_env("ROBOTOPS_AGENT_MAX_TOOL_ITERATIONS", 4)
    return AgentSettings(
        llm_enabled=bool(api_key) and llm_flag not in {"0", "false", "no", "off"},
        deepseek_api_key=api_key,
        llm_model=os.getenv("ROBOTOPS_LLM_MODEL", "deepseek-v4-flash"),
        max_tool_iterations=max(0, max_tool_iterations),
        log_service_url=os.getenv("ROBOTOPS_LOG_SERVICE_URL", "http://127.0.0.1:9501").rstrip("/"),
        tool_timeout_seconds=max(0.1, _float_env("ROBOTOPS_AGENT_TOOL_TIMEOUT_SECONDS", 5.0)),
        source_search_roots=_source_roots_env(),
        case_search_roots=_case_roots_env(),
        knowledge_search_roots=_knowledge_roots_env(),
    )


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name, "")
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name, "")
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _source_roots_env() -> tuple[str, ...]:
    value = os.getenv("ROBOTOPS_SOURCE_SEARCH_ROOTS", "")
    if not value:
        return ("../interaction", "../aimrt_agent/aimrt_agent/interaction")
    return tuple(item.strip() for item in value.split(":") if item.strip())


def _case_roots_env() -> tuple[str, ...]:
    value = os.getenv("ROBOTOPS_CASE_SEARCH_ROOTS", "")
    if not value:
        return ("knowledge/cases", "docs/cases")
    return tuple(item.strip() for item in value.split(":") if item.strip())


def _knowledge_roots_env() -> tuple[str, ...]:
    value = os.getenv("ROBOTOPS_KNOWLEDGE_SEARCH_ROOTS", "")
    if not value:
        return ("knowledge/articles", "docs/knowledge")
    return tuple(item.strip() for item in value.split(":") if item.strip())
