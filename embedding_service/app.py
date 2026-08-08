from __future__ import annotations

import math
import os
from threading import Lock, Thread
from typing import List, Union

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

try:
    from fastembed import TextEmbedding
except ImportError:  # pragma: no cover - reported through the health endpoint
    TextEmbedding = None  # type: ignore[assignment,misc]


MODEL_NAME = os.getenv("ROBOTOPS_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
MODEL_CACHE_DIR = os.getenv("ROBOTOPS_EMBEDDING_CACHE_DIR", "") or None
MAX_BATCH_SIZE = max(1, int(os.getenv("ROBOTOPS_EMBEDDING_MAX_BATCH_SIZE", "32")))
PRELOAD_MODEL = os.getenv("ROBOTOPS_EMBEDDING_PRELOAD", "false").strip().lower() in {"1", "true", "yes", "on"}

app = FastAPI(title="RobotOps Embedding Service", version="1.0.0")
_model = None
_model_lock = Lock()
_model_error = ""
_embedding_requests = 0
_embedding_failures = 0
_embedded_inputs = 0


class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]] = Field(min_length=1)
    model: str = ""


def _get_model():
    global _model, _model_error
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
                    _model_error = ""
                except Exception as exc:  # model download/load errors are service-unavailable
                    _model_error = str(exc)
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
        "status": "ready" if _model is not None else "degraded",
        "service": "embedding-service",
        "model": MODEL_NAME,
        "ready": _model is not None,
        "error": _model_error or None,
        "provider": "fastembed",
    }


@app.get("/ready")
def ready():
    if _model is None:
        raise HTTPException(status_code=503, detail=_model_error or "embedding model is not loaded")
    return {"status": "ready", "service": "embedding-service", "model": MODEL_NAME}


@app.post("/warmup")
def warmup():
    """Explicitly load the model; readiness probes never trigger downloads."""
    try:
        _get_model()
    except HTTPException as exc:
        raise HTTPException(status_code=503, detail=exc.detail) from exc
    return {"status": "ready", "service": "embedding-service", "model": MODEL_NAME}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    # Keep metrics dependency-free; this is scrape-compatible with Prometheus.
    return (
        "# TYPE robotops_embedding_ready gauge\n"
        f"robotops_embedding_ready {int(_model is not None)}\n"
        "# TYPE robotops_embedding_requests_total counter\n"
        f"robotops_embedding_requests_total {_embedding_requests}\n"
        "# TYPE robotops_embedding_failures_total counter\n"
        f"robotops_embedding_failures_total {_embedding_failures}\n"
        "# TYPE robotops_embedding_inputs_total counter\n"
        f"robotops_embedding_inputs_total {_embedded_inputs}\n"
    )


@app.post("/v1/embeddings")
def embeddings(payload: EmbeddingRequest):
    global _embedding_requests, _embedding_failures, _embedded_inputs
    _embedding_requests += 1
    texts = [payload.input] if isinstance(payload.input, str) else payload.input
    if not texts or any(not text.strip() for text in texts):
        _embedding_failures += 1
        raise HTTPException(status_code=400, detail="input must contain non-empty text")
    if len(texts) > MAX_BATCH_SIZE:
        _embedding_failures += 1
        raise HTTPException(status_code=400, detail=f"input batch exceeds {MAX_BATCH_SIZE}")

    try:
        model = _get_model()
    except HTTPException:
        _embedding_failures += 1
        raise
    try:
        vectors = [_normalize(vector) for vector in model.embed(texts)]
    except Exception as exc:
        _embedding_failures += 1
        raise HTTPException(status_code=503, detail=f"embedding inference failed: {exc}") from exc
    if len(vectors) != len(texts):
        _embedding_failures += 1
        raise HTTPException(status_code=503, detail="embedding provider returned an invalid batch")
    _embedded_inputs += len(texts)

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


@app.on_event("startup")
def preload_model() -> None:
    if not PRELOAD_MODEL:
        return

    def load_in_background() -> None:
        try:
            _get_model()
        except HTTPException:
            # Liveness remains available and the next readiness/request can retry.
            return

    Thread(target=load_in_background, name="embedding-model-warmup", daemon=True).start()
