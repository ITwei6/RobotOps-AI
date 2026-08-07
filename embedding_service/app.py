from __future__ import annotations

import math
import os
from threading import Lock
from typing import List, Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from fastembed import TextEmbedding
except ImportError:  # pragma: no cover - reported through the health endpoint
    TextEmbedding = None  # type: ignore[assignment,misc]


MODEL_NAME = os.getenv("ROBOTOPS_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
MODEL_CACHE_DIR = os.getenv("ROBOTOPS_EMBEDDING_CACHE_DIR", "") or None
MAX_BATCH_SIZE = max(1, int(os.getenv("ROBOTOPS_EMBEDDING_MAX_BATCH_SIZE", "32")))

app = FastAPI(title="RobotOps Embedding Service", version="1.0.0")
_model = None
_model_lock = Lock()


class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]] = Field(min_length=1)
    model: str = ""


def _get_model():
    global _model
    if TextEmbedding is None:
        raise HTTPException(status_code=503, detail="fastembed is not installed")
    if _model is None:
        with _model_lock:
            if _model is None:
                kwargs = {"model_name": MODEL_NAME}
                if MODEL_CACHE_DIR:
                    kwargs["cache_dir"] = MODEL_CACHE_DIR
                try:
                    _model = TextEmbedding(**kwargs)
                except Exception as exc:  # model download/load errors are service-unavailable
                    raise HTTPException(status_code=503, detail=f"embedding model unavailable: {exc}") from exc
    return _model


def _normalize(vector) -> List[float]:
    values = [float(value) for value in vector]
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        return values
    return [value / norm for value in values]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "embedding-service",
        "model": MODEL_NAME,
        "ready": _model is not None,
        "provider": "fastembed",
    }


@app.post("/v1/embeddings")
def embeddings(payload: EmbeddingRequest):
    texts = [payload.input] if isinstance(payload.input, str) else payload.input
    if not texts or any(not text.strip() for text in texts):
        raise HTTPException(status_code=400, detail="input must contain non-empty text")
    if len(texts) > MAX_BATCH_SIZE:
        raise HTTPException(status_code=400, detail=f"input batch exceeds {MAX_BATCH_SIZE}")

    model = _get_model()
    try:
        vectors = [_normalize(vector) for vector in model.embed(texts)]
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"embedding inference failed: {exc}") from exc
    if len(vectors) != len(texts):
        raise HTTPException(status_code=503, detail="embedding provider returned an invalid batch")

    return {
        "object": "list",
        "model": payload.model or MODEL_NAME,
        "data": [
            {"object": "embedding", "embedding": vector, "index": index}
            for index, vector in enumerate(vectors)
        ],
        "usage": {
            "prompt_tokens": 0,
            "total_tokens": 0,
        },
    }
