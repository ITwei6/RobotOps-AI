from __future__ import annotations

from typing import Any, Callable, Dict, List, Sequence

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from agent_service.app.source_registry import load_repositories
from agent_service.app.tools import fetch_log_context, search_cases, search_knowledge, search_source


class LogContextToolInput(BaseModel):
    bug_id: str = ""
    log_package_id: str = ""
    occurred_time: int = 0
    module_name: str = ""
    seconds_before: int = 300
    seconds_after: int = 300
    keywords: List[str] = Field(default_factory=list)


class SourceSearchToolInput(BaseModel):
    module_name: str
    branch: str = ""
    commit: str = ""
    keywords: List[str] = Field(default_factory=list)
    max_results: int = 10


class CaseSearchToolInput(BaseModel):
    title: str = ""
    description: str = ""
    robot_type: str = ""
    main_module: str = ""
    keywords: List[str] = Field(default_factory=list)
    max_results: int = 5


class KnowledgeSearchToolInput(BaseModel):
    title: str = ""
    description: str = ""
    main_module: str = ""
    keywords: List[str] = Field(default_factory=list)
    max_results: int = 5


def build_tool_registry(
    *,
    log_service_url: str,
    timeout_seconds: float,
    source_roots: Sequence[str],
    source_workspace_root: str,
    source_repository_file: str,
    case_roots: Sequence[str],
    knowledge_roots: Sequence[str],
    log_fetcher: Callable[..., Dict[str, Any]] = fetch_log_context,
    source_searcher: Callable[..., Dict[str, Any]] = search_source,
    case_searcher: Callable[..., Dict[str, Any]] = search_cases,
    knowledge_searcher: Callable[..., Dict[str, Any]] = search_knowledge,
) -> Dict[str, StructuredTool]:
    repositories = load_repositories(source_repository_file)

    def log_context(**args: Any) -> Dict[str, Any]:
        return log_fetcher(
            log_service_url=log_service_url,
            timeout_seconds=timeout_seconds,
            args=args,
        )

    def source_search(**args: Any) -> Dict[str, Any]:
        return source_searcher(
            roots=source_roots,
            timeout_seconds=timeout_seconds,
            args=args,
            workspace_root=source_workspace_root,
            repositories=repositories,
        )

    def case_search(**args: Any) -> Dict[str, Any]:
        return case_searcher(case_roots, args)

    def knowledge_search(**args: Any) -> Dict[str, Any]:
        return knowledge_searcher(knowledge_roots, args)

    return {
        "log_context": StructuredTool.from_function(
            func=log_context,
            name="log_context",
            description="按日志包和发生时间获取多个机器人模块的日志上下文。",
            args_schema=LogContextToolInput,
        ),
        "source_search": StructuredTool.from_function(
            func=source_search,
            name="source_search",
            description="在指定模块的本地源码仓库中检索日志关键句并返回源码证据。",
            args_schema=SourceSearchToolInput,
        ),
        "case_search": StructuredTool.from_function(
            func=case_search,
            name="case_search",
            description="检索相同机器人类型和模块的历史诊断案例。",
            args_schema=CaseSearchToolInput,
        ),
        "knowledge_search": StructuredTool.from_function(
            func=knowledge_search,
            name="knowledge_search",
            description="检索模块 SOP、错误码和排障知识。",
            args_schema=KnowledgeSearchToolInput,
        ),
    }
