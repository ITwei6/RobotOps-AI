from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSettings:
    llm_enabled: bool
    deepseek_api_key: str
    llm_model: str
    max_tool_iterations: int


def load_settings() -> AgentSettings:
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    llm_flag = os.getenv("ROBOTOPS_LLM_ENABLED", "true").strip().lower()
    max_tool_iterations = _int_env("ROBOTOPS_AGENT_MAX_TOOL_ITERATIONS", 2)
    return AgentSettings(
        llm_enabled=bool(api_key) and llm_flag not in {"0", "false", "no", "off"},
        deepseek_api_key=api_key,
        llm_model=os.getenv("ROBOTOPS_LLM_MODEL", "deepseek-v4-flash"),
        max_tool_iterations=max(0, max_tool_iterations),
    )


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name, "")
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default
