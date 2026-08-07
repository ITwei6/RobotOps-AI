from __future__ import annotations

from typing import Any, Dict, Sequence

from agent_service.app.rag_retriever import LocalHybridRetriever, load_documents


def search_cases(roots: Sequence[str], args: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve historical cases with transparent hybrid RAG scoring."""
    query = _query_text(args)
    main_module = str(args.get("main_module") or "").strip().lower()
    limit = max(1, min(int(args.get("max_results") or 5), 20))
    documents = load_documents(roots, collection="cases")
    matches = LocalHybridRetriever(documents).search(query, module=main_module, limit=limit)
    response = {"ok": True, "history_cases": matches}
    if documents:
        response["retrieval"] = {"method": "hybrid_bm25_tfidf", "documents": len(documents)}
    return response


def _query_text(args: Dict[str, Any]) -> str:
    values = [args.get("title", ""), args.get("description", ""), " ".join(str(item) for item in args.get("keywords") or [])]
    return " ".join(str(value) for value in values if value).strip().lower()
