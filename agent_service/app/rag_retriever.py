from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterable, List, Sequence


_DOCUMENT_CACHE: Dict[tuple[str, tuple[str, ...]], tuple[tuple[tuple[str, int, int], ...], List[Dict[str, Any]]]] = {}
_CACHE_LOCK = RLock()


class LocalHybridRetriever:
    """Small dependency-free RAG retriever for cases, SOPs and fault knowledge.

    BM25 keeps identifiers and error codes precise. The sparse TF-IDF cosine
    score gives short Chinese/English paraphrases a second retrieval signal.
    The result is intentionally transparent so the Agent can cite the source
    document without treating retrieved context as current incident evidence.
    """

    def __init__(self, documents: Sequence[Dict[str, Any]]) -> None:
        self.documents = [dict(document) for document in documents]
        self.tokenized = [_tokens(str(document.get("_search_text") or "")) for document in self.documents]
        self.document_frequency: Counter[str] = Counter()
        for tokens in self.tokenized:
            self.document_frequency.update(set(tokens))
        self.average_length = sum(len(tokens) for tokens in self.tokenized) / max(len(self.tokenized), 1)

    def search(self, query: str, *, module: str = "", limit: int = 5) -> List[Dict[str, Any]]:
        query_tokens = _tokens(query)
        if not query_tokens or not self.documents:
            return []
        query_counts = Counter(query_tokens)
        candidates: List[tuple[float, float, float, Dict[str, Any]]] = []
        for index, document in enumerate(self.documents):
            item_module = str(document.get("main_module") or document.get("module") or "").casefold()
            module_bonus = 0.25 if module and module.casefold() == item_module else 0.0
            bm25 = self._bm25(query_counts, self.tokenized[index])
            cosine = self._cosine(query_counts, self.tokenized[index])
            if bm25 <= 0 and cosine <= 0 and module_bonus <= 0:
                continue
            score = min(1.0, 0.62 * _normalize_bm25(bm25) + 0.28 * cosine + module_bonus)
            result = dict(document)
            result.pop("_search_text", None)
            result["match_score"] = round(score, 4)
            result["retrieval"] = {
                "method": "hybrid_bm25_tfidf",
                "bm25_score": round(bm25, 4),
                "vector_score": round(cosine, 4),
                "module_bonus": module_bonus,
            }
            candidates.append((score, bm25, cosine, result))
        candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        results: List[Dict[str, Any]] = []
        for rank, (_, _, _, item) in enumerate(candidates[: max(1, min(limit, 20))], start=1):
            item["retrieval"]["rank"] = rank
            results.append(item)
        return results

    def _bm25(self, query: Counter[str], document: List[str]) -> float:
        counts = Counter(document)
        length = len(document)
        score = 0.0
        k1, b = 1.5, 0.75
        total = max(len(self.documents), 1)
        for token, query_frequency in query.items():
            frequency = counts.get(token, 0)
            if not frequency:
                continue
            idf = math.log(1 + (total - self.document_frequency.get(token, 0) + 0.5) / (self.document_frequency.get(token, 0) + 0.5))
            saturation = frequency * (k1 + 1) / max(frequency + k1 * (1 - b + b * length / max(self.average_length, 1)), 1e-9)
            score += idf * saturation * min(query_frequency, 2)
        return score

    def _cosine(self, query: Counter[str], document: List[str]) -> float:
        counts = Counter(document)
        query_norm = 0.0
        document_norm = 0.0
        dot = 0.0
        total = max(len(self.documents), 1)
        for token, frequency in query.items():
            idf = math.log(1 + total / (1 + self.document_frequency.get(token, 0)))
            query_weight = frequency * idf
            document_weight = counts.get(token, 0) * idf
            dot += query_weight * document_weight
            query_norm += query_weight * query_weight
        for token, frequency in counts.items():
            idf = math.log(1 + total / (1 + self.document_frequency.get(token, 0)))
            document_norm += (frequency * idf) ** 2
        return dot / math.sqrt(query_norm * document_norm) if query_norm and document_norm else 0.0


def load_documents(roots: Sequence[str], *, collection: str) -> List[Dict[str, Any]]:
    cache_key = (collection, tuple(str(Path(root).expanduser()) for root in roots))
    paths = _document_paths(roots)
    signature = tuple(_path_signature(path) for path in paths)
    with _CACHE_LOCK:
        cached = _DOCUMENT_CACHE.get(cache_key)
        if cached and cached[0] == signature:
            return [dict(document) for document in cached[1]]

    documents: List[Dict[str, Any]] = []
    for path in paths:
        try:
            values = _read_values(path, collection)
        except (OSError, UnicodeError, ValueError, TypeError):
            continue
        for index, value in enumerate(values):
            if not isinstance(value, dict):
                continue
            item = dict(value)
            item.setdefault("source", item.get("source_id") or item.get("case_id") or str(path))
            item.setdefault("document_id", item.get("id") or item.get("case_id") or item.get("source_id") or f"{path}:{index}")
            item["_search_text"] = " ".join(_flatten_text(item))
            documents.append(item)
    with _CACHE_LOCK:
        _DOCUMENT_CACHE[cache_key] = (signature, [dict(document) for document in documents])
    return documents


def _document_paths(roots: Sequence[str]) -> List[Path]:
    paths: List[Path] = []
    for root_value in roots:
        root = Path(root_value).expanduser()
        if not root.exists():
            continue
        paths.extend([root] if root.is_file() else sorted(root.rglob("*.json")) + sorted(root.rglob("*.jsonl")))
    return paths


def _path_signature(path: Path) -> tuple[str, int, int]:
    try:
        stat = path.stat()
        return str(path), int(stat.st_mtime_ns), int(stat.st_size)
    except OSError:
        return str(path), 0, 0


def _read_values(path: Path, collection: str) -> List[Any]:
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get(collection, [])
    return value if isinstance(value, list) else [value]


def _flatten_text(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key != "_search_text":
                yield from _flatten_text(child)
    elif isinstance(value, list):
        for child in value:
            yield from _flatten_text(child)
    elif value is not None:
        yield str(value)


def _tokens(value: str) -> List[str]:
    words = [item.casefold() for item in re.split(r"[^a-zA-Z0-9_\u4e00-\u9fff]+", value) if item]
    result: List[str] = []
    for word in words:
        if len(word) > 1 and any("\u4e00" <= char <= "\u9fff" for char in word):
            result.extend(word[index : index + 2] for index in range(len(word) - 1))
        else:
            result.append(word)
    return list(dict.fromkeys(result))


def _normalize_bm25(value: float) -> float:
    return value / (value + 1.0) if value > 0 else 0.0
