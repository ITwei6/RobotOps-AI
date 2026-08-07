from __future__ import annotations

import base64
import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Sequence
from urllib import error, request

from agent_service.app.rag_retriever import LocalHybridRetriever, load_documents


class RagBackendUnavailable(RuntimeError):
    pass


class EmbeddingClient:
    """OpenAI-compatible embedding adapter; provider details stay in env vars."""

    def __init__(self, *, url: str, api_key: str, model: str, timeout: float, dimensions: int) -> None:
        self.url = url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.dimensions = dimensions

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.model)

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        if not self.enabled:
            raise RagBackendUnavailable("embedding provider is not configured")
        endpoint = self.url if self.url.endswith("/embeddings") else f"{self.url}/embeddings"
        payload = {"model": self.model, "input": list(texts)}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            with request.urlopen(request.Request(endpoint, data=body, headers=headers, method="POST"), timeout=self.timeout) as response:
                value = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RagBackendUnavailable(f"embedding request failed: {exc}") from exc
        vectors = [item.get("embedding") for item in sorted(value.get("data") or [], key=lambda item: int(item.get("index") or 0))]
        if len(vectors) != len(texts) or any(not isinstance(vector, list) for vector in vectors):
            raise RagBackendUnavailable("embedding response has invalid dimensions")
        if any(len(vector) != self.dimensions for vector in vectors):
            raise RagBackendUnavailable("embedding dimensions do not match ES mapping")
        return [[float(value) for value in vector] for vector in vectors]


class ElasticsearchRagStore:
    def __init__(self, *, url: str, user: str, password: str, index_prefix: str, timeout: float, embedding: EmbeddingClient | None = None) -> None:
        self.url = url.rstrip("/")
        self.user = user
        self.password = password
        self.index_prefix = index_prefix
        self.timeout = timeout
        self.embedding = embedding

    def index_name(self, collection: str) -> str:
        dimensions = self.embedding.dimensions if self.embedding else 384
        model_tag = hashlib.sha1((self.embedding.model if self.embedding else "lexical").encode()).hexdigest()[:8]
        return f"{self.index_prefix}-{collection}-v1-d{dimensions}-{model_tag}".lower().replace("_", "-")

    def ensure_index(self, collection: str) -> None:
        mapping = {
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {"properties": {
                "collection": {"type": "keyword"}, "document_id": {"type": "keyword"},
                "chunk_id": {"type": "keyword"}, "content": {"type": "text"},
                "title": {"type": "text"}, "source": {"type": "keyword"},
                "source_type": {"type": "keyword"}, "main_module": {"type": "keyword"},
                "robot_type": {"type": "keyword"}, "software_version": {"type": "keyword"},
                "branch": {"type": "keyword"}, "commit": {"type": "keyword"},
                "content_hash": {"type": "keyword"}, "updated_at": {"type": "date"},
                "embedding": {"type": "dense_vector", "dims": self.embedding.dimensions if self.embedding else 384, "index": False},
            }},
        }
        try:
            self._request("PUT", f"/{self.index_name(collection)}", mapping)
        except RagBackendUnavailable as exc:
            if "resource_already_exists" not in str(exc) and "already exists" not in str(exc):
                raise

    def bulk_index(self, collection: str, documents: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        values = [item for item in documents]
        if not values:
            return {"indexed": 0, "chunks": 0, "embedding": False}
        self.ensure_index(collection)
        chunks = [chunk for document in values for chunk in _chunks(document, collection)]
        vectors: List[List[float]] = []
        embedding_enabled = bool(self.embedding and self.embedding.enabled)
        if embedding_enabled:
            vectors = self.embedding.embed([chunk["content"] for chunk in chunks])
        lines: List[str] = []
        for index, chunk in enumerate(chunks):
            if vectors:
                chunk["embedding"] = vectors[index]
            lines.append(json.dumps({"index": {"_index": self.index_name(collection), "_id": chunk["chunk_id"]}}))
            lines.append(json.dumps(chunk, ensure_ascii=False))
        response = self._request("POST", "/_bulk?refresh=wait_for", "\n".join(lines) + "\n", raw=True)
        if response.get("errors"):
            raise RagBackendUnavailable("bulk RAG index contains failed operations")
        return {"indexed": len(values), "chunks": len(chunks), "embedding": bool(vectors)}

    def search(self, collection: str, query: str, *, module: str = "", robot_type: str = "", software_version: str = "", branch: str = "", limit: int = 5) -> Dict[str, Any]:
        if not query.strip():
            return {"results": [], "retrieval": {"method": "elasticsearch_empty_query", "backend": "elasticsearch", "index": self.index_name(collection), "embedding": False}}
        self.ensure_index(collection)
        filters: List[Dict[str, Any]] = []
        if module:
            filters.append({"term": {"main_module": module}})
        if robot_type:
            filters.append({"term": {"robot_type": robot_type}})
        if software_version:
            filters.append({"term": {"software_version": software_version}})
        if branch:
            filters.append({"term": {"branch": branch}})
        query_vector: List[float] = []
        embedding_error = ""
        if self.embedding and self.embedding.enabled:
            try:
                query_vector = self.embedding.embed([query])[0]
            except RagBackendUnavailable as exc:
                embedding_error = str(exc)
        bool_query = {"bool": {"filter": filters, "should": [{"multi_match": {"query": query, "fields": ["content^3", "title^2", "source"]}}], "minimum_should_match": 0}}
        body: Dict[str, Any] = {"size": max(1, min(limit, 20)), "query": bool_query, "_source": {"excludes": ["embedding"]}}
        if query_vector:
            body["query"] = {"script_score": {"query": bool_query, "script": {"source": "0.65 * _score + 0.35 * (cosineSimilarity(params.query_vector, 'embedding') + 1.0)", "params": {"query_vector": query_vector}}}}
        try:
            response = self._request("POST", f"/{self.index_name(collection)}/_search", body)
        except RagBackendUnavailable as exc:
            if not query_vector:
                raise
            embedding_error = str(exc)
            response = self._request("POST", f"/{self.index_name(collection)}/_search", {"size": body["size"], "query": bool_query, "_source": body["_source"]})
        results: List[Dict[str, Any]] = []
        for rank, hit in enumerate(response.get("hits", {}).get("hits", []), start=1):
            item = dict(hit.get("_source") or {})
            item["match_score"] = round(float(hit.get("_score") or 0.0), 4)
            item["retrieval"] = {"method": "elasticsearch_hybrid" if query_vector else "elasticsearch_bm25", "rank": rank, "backend": "elasticsearch"}
            if embedding_error:
                item["retrieval"]["embedding_fallback"] = embedding_error
            results.append(item)
        return {"results": results, "retrieval": {"method": "elasticsearch_hybrid" if query_vector else "elasticsearch_bm25", "backend": "elasticsearch", "index": self.index_name(collection), "embedding": bool(query_vector)}}

    def _request(self, method: str, path: str, payload: Any, *, raw: bool = False) -> Dict[str, Any]:
        headers = {"Content-Type": "application/x-ndjson" if raw else "application/json"}
        if self.user:
            token = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"
        body = payload.encode("utf-8") if raw and isinstance(payload, str) else payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            with request.urlopen(request.Request(f"{self.url}{path}", data=body, headers=headers, method=method), timeout=self.timeout) as response:
                content = response.read()
                return json.loads(content.decode("utf-8")) if content else {}
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RagBackendUnavailable(f"Elasticsearch HTTP {exc.code}: {detail[:300]}") from exc
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RagBackendUnavailable(f"Elasticsearch request failed: {exc}") from exc


def build_store(settings: Any) -> ElasticsearchRagStore:
    embedding = EmbeddingClient(
        url=settings.rag_embedding_url,
        api_key=settings.rag_embedding_api_key,
        model=settings.rag_embedding_model,
        timeout=settings.tool_timeout_seconds,
        dimensions=settings.rag_embedding_dimensions,
    )
    return ElasticsearchRagStore(
        url=settings.rag_elasticsearch_url,
        user=settings.rag_elasticsearch_user,
        password=settings.rag_elasticsearch_password,
        index_prefix=settings.rag_index_prefix,
        timeout=settings.tool_timeout_seconds,
        embedding=embedding,
    )


def retrieve_collection(*, roots: Sequence[str], args: Dict[str, Any], collection: str, settings: Any) -> Dict[str, Any]:
    query = _query_text(args)
    module = str(args.get("main_module") or "")
    robot_type = str(args.get("robot_type") or "")
    software_version = str(args.get("software_version") or "")
    branch = str(args.get("branch") or "")
    limit = max(1, min(int(args.get("max_results") or 5), 20))
    if settings.rag_backend == "elasticsearch" and settings.rag_elasticsearch_password:
        try:
            store = build_store(settings)
            result = store.search(collection, query, module=module, robot_type=robot_type, software_version=software_version, branch=branch, limit=limit)
            return {"results": result["results"], "retrieval": result["retrieval"]}
        except RagBackendUnavailable as exc:
            fallback = _local_collection(roots, collection, query, module, limit)
            fallback["retrieval"] = {
                "method": "elasticsearch_fallback_local",
                "backend": "local",
                "fallback_reason": str(exc)[:300],
                "documents": fallback["retrieval"]["documents"],
            }
            return fallback
    return _local_collection(roots, collection, query, module, limit)


def index_collection(*, roots: Sequence[str], collection: str, settings: Any) -> Dict[str, Any]:
    documents = load_documents(roots, collection=collection)
    store = build_store(settings)
    return store.bulk_index(collection, documents)


def _chunks(document: Dict[str, Any], collection: str, *, max_chars: int = 1200, overlap: int = 120) -> Iterable[Dict[str, Any]]:
    content_fields = ("title", "content", "description", "summary", "causes", "actions", "recommended_actions", "solution", "resolution")
    content = " ".join(str(document.get(field) or "") for field in content_fields).strip()
    if not content:
        content = " ".join(str(value) for value in document.values())
    content = content.strip()
    if not content:
        return []
    document_id = str(document.get("document_id") or document.get("id") or document.get("case_id") or document.get("source_id") or hashlib.sha256(content.encode()).hexdigest()[:16])
    values = []
    start = 0
    while start < len(content):
        end = min(len(content), start + max_chars)
        chunk_text = content[start:end]
        chunk_id = hashlib.sha256(f"{collection}:{document_id}:{start}:{chunk_text}".encode()).hexdigest()
        values.append({
            "collection": collection, "document_id": document_id, "chunk_id": chunk_id,
            "content": chunk_text, "title": str(document.get("title") or ""),
            "source": str(document.get("source") or document.get("source_id") or document_id),
            "source_type": "history_case" if collection == "cases" else "knowledge",
            "main_module": str(document.get("main_module") or document.get("module") or ""),
            "robot_type": str(document.get("robot_type") or ""),
            "software_version": str(document.get("software_version") or ""),
            "branch": str(document.get("branch") or ""), "commit": str(document.get("commit") or ""),
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        if end == len(content):
            break
        start = max(start + 1, end - overlap)
    return values


def _query_text(args: Dict[str, Any]) -> str:
    return " ".join(str(value) for value in [args.get("title", ""), args.get("description", ""), " ".join(str(item) for item in args.get("keywords") or [])] if value).strip()


def _local_collection(roots: Sequence[str], collection: str, query: str, module: str, limit: int) -> Dict[str, Any]:
    documents = load_documents(roots, collection=collection)
    results = LocalHybridRetriever(documents).search(query, module=module, limit=limit)
    return {"results": results, "retrieval": {"method": "hybrid_bm25_tfidf", "backend": "local", "documents": len(documents)}}
