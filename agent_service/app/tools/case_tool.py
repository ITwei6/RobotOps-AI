from __future__ import annotations

from typing import Any, Dict, Sequence

from agent_service.app.industrial_rag import retrieve_collection
from agent_service.app.settings import load_settings


def search_cases(roots: Sequence[str], args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve historical cases with transparent hybrid RAG scoring."""
    query = _query_text(args)
    main_module = str(args.get("main_module") or "").strip().lower()
    limit = max(1, min(int(args.get("max_results") or 5), 20))
    result = retrieve_collection(roots=roots, args=args, collection="cases", settings=load_settings())
    response = {"ok": True, "history_cases": result["results"]}
    if result.get("retrieval", {}).get("documents", 0) or result.get("retrieval", {}).get("backend") == "elasticsearch":
        response["retrieval"] = result["retrieval"]
    return response


def _query_text(args: Dict[str, Any]) -> str:
    values = [args.get("title", ""), args.get("description", ""), " ".join(str(item) for item in args.get("keywords") or [])]
    return " ".join(str(value) for value in values if value).strip().lower()
