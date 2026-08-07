from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSettings:
    llm_enabled: bool
    deepseek_api_key: str
    llm_model: str
    max_tool_iterations: int
    max_source_analysis_iterations: int
    log_service_url: str
    tool_timeout_seconds: float
    source_search_roots: tuple[str, ...]
    source_workspace_root: str
    source_index_root: str
    source_repository_file: str
    case_search_roots: tuple[str, ...]
    knowledge_search_roots: tuple[str, ...]
    rag_backend: str
    rag_elasticsearch_url: str
    rag_elasticsearch_user: str
    rag_elasticsearch_password: str
    rag_index_prefix: str
    rag_embedding_url: str
    rag_embedding_api_key: str
    rag_embedding_model: str
    rag_embedding_dimensions: int


def load_settings() -> AgentSettings:
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    llm_flag = os.getenv("ROBOTOPS_LLM_ENABLED", "true").strip().lower()
    # A time-window diagnosis may need log collection, primary-source search,
    # related-module searches, case retrieval, and knowledge retrieval.
    max_tool_iterations = _int_env("ROBOTOPS_AGENT_MAX_TOOL_ITERATIONS", 8)
    max_source_analysis_iterations = _int_env("ROBOTOPS_AGENT_MAX_SOURCE_ANALYSIS_ITERATIONS", 3)
    return AgentSettings(
        llm_enabled=bool(api_key) and llm_flag not in {"0", "false", "no", "off"},
        deepseek_api_key=api_key,
        llm_model=os.getenv("ROBOTOPS_LLM_MODEL", "deepseek-v4-flash"),
        max_tool_iterations=max(0, max_tool_iterations),
        max_source_analysis_iterations=max(0, max_source_analysis_iterations),
        log_service_url=os.getenv("ROBOTOPS_LOG_SERVICE_URL", "http://127.0.0.1:9501").rstrip("/"),
        tool_timeout_seconds=max(0.1, _float_env("ROBOTOPS_AGENT_TOOL_TIMEOUT_SECONDS", 5.0)),
        source_search_roots=_source_roots_env(),
        source_workspace_root=os.getenv("ROBOTOPS_SOURCE_WORKSPACE_ROOT", ".robotops/source-cache"),
        source_index_root=os.getenv("ROBOTOPS_SOURCE_INDEX_ROOT", ".robotops/source-index"),
        source_repository_file=os.getenv("ROBOTOPS_SOURCE_REPOSITORY_FILE", ".robotops/source-repositories.json"),
        case_search_roots=_case_roots_env(),
        knowledge_search_roots=_knowledge_roots_env(),
        rag_backend=os.getenv("ROBOTOPS_RAG_BACKEND", "local").strip().lower(),
        rag_elasticsearch_url=os.getenv("ROBOTOPS_RAG_ELASTICSEARCH_URL", "http://127.0.0.1:9200").rstrip("/"),
        rag_elasticsearch_user=os.getenv("ROBOTOPS_RAG_ELASTICSEARCH_USER", "elastic"),
        rag_elasticsearch_password=os.getenv("ROBOTOPS_RAG_ELASTICSEARCH_PASSWORD", ""),
        rag_index_prefix=os.getenv("ROBOTOPS_RAG_INDEX_PREFIX", "robotops-rag"),
        rag_embedding_url=os.getenv("ROBOTOPS_RAG_EMBEDDING_URL", "").rstrip("/"),
        rag_embedding_api_key=os.getenv("ROBOTOPS_RAG_EMBEDDING_API_KEY", ""),
        rag_embedding_model=os.getenv("ROBOTOPS_RAG_EMBEDDING_MODEL", ""),
        rag_embedding_dimensions=max(8, _int_env("ROBOTOPS_RAG_EMBEDDING_DIMENSIONS", 384)),
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
