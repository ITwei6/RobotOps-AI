#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_service.app.industrial_rag import index_collection
from agent_service.app.settings import load_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Index RobotOps case/knowledge documents into the configured RAG backend.")
    parser.add_argument("--collection", choices=("cases", "items"), required=True)
    parser.add_argument("--root", action="append", required=True, help="JSON/JSONL file or directory; repeatable")
    args = parser.parse_args()
    settings = load_settings()
    if settings.rag_backend != "elasticsearch":
        parser.error("set ROBOTOPS_RAG_BACKEND=elasticsearch before indexing")
    try:
        result = index_collection(roots=tuple(args.root), collection=args.collection, settings=settings)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "collection": args.collection, **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
