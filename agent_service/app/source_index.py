from __future__ import annotations

import fcntl
import hashlib
import json
import re
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Set, Tuple


INDEX_SCHEMA_VERSION = 2
MAX_INDEX_FILE_BYTES = 2 * 1024 * 1024
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".py"}
IGNORED_DIRECTORIES = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    "build",
    "cmake-build-debug",
    "cmake-build-release",
    "node_modules",
    "third_party",
}

_INDEX_LOCK = threading.Lock()


def refresh_source_index(
    *,
    repository_root: Path,
    index_root: str,
    revision: str,
    file_indexer: Callable[[Path], Dict[str, Any]],
    timeout_seconds: float,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    root = repository_root.resolve()
    index_path = _index_path(Path(index_root).expanduser(), root)

    with _INDEX_LOCK, _file_lock(index_path):
        previous = _load_index(index_path, root)
        previous_files = dict(previous.get("files") or {})
        previous_revision = str(previous.get("revision") or "")
        revision_changed = previous_revision != revision
        revision_paths = _revision_changed_paths(
            root,
            previous_revision,
            revision,
            timeout_seconds,
        ) if previous_files and revision_changed else set()
        force_all = bool(previous_files and revision_changed and revision_paths is None)

        current_paths = _source_paths(root)
        current_relatives = {path.relative_to(root).as_posix() for path in current_paths}
        removed_files = sorted(set(previous_files) - current_relatives)
        indexed_files: Dict[str, Dict[str, Any]] = {}
        changed_files: List[str] = []

        for path in current_paths:
            relative = path.relative_to(root).as_posix()
            stat = path.stat()
            old = previous_files.get(relative) or {}
            metadata_matches = (
                int(old.get("size") or -1) == stat.st_size
                and int(old.get("mtime_ns") or -1) == stat.st_mtime_ns
            )
            forced_by_revision = force_all or bool(revision_paths and relative in revision_paths)
            if old and metadata_matches and not forced_by_revision:
                indexed_files[relative] = old
                continue

            record = file_indexer(path)
            record.update(
                {
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                    "content_sha256": _file_sha256(path),
                }
            )
            indexed_files[relative] = record
            changed_files.append(relative)

        workspace_revision = _workspace_revision(indexed_files)
        index = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "repository_root": str(root),
            "revision": revision,
            "workspace_revision": workspace_revision,
            "generated_at": int(time.time() * 1000),
            "files": indexed_files,
        }
        action = "reused"
        if not previous_files:
            action = "built"
        elif changed_files or removed_files or revision_changed:
            action = "updated"

        if action != "reused":
            _write_index(index_path, index)
        else:
            index["generated_at"] = int(previous.get("generated_at") or index["generated_at"])

    status = {
        "ok": True,
        "enabled": True,
        "action": action,
        "revision": revision,
        "previous_revision": previous_revision,
        "workspace_revision": workspace_revision,
        "file_count": len(indexed_files),
        "changed_files": changed_files,
        "removed_files": removed_files,
    }
    return index, status


def search_source_index(
    index: Dict[str, Any],
    query: str,
    *,
    max_results: int,
) -> List[Dict[str, Any]]:
    normalized = _normalize_query(query)
    if not normalized:
        return []
    query_tail = _symbol_tail(normalized)
    matches: List[Dict[str, Any]] = []

    for relative, record in (index.get("files") or {}).items():
        for symbol in record.get("symbols") or []:
            score = _symbol_score(normalized, query_tail, str(symbol.get("name") or ""))
            if score:
                matches.append(
                    _match(relative, symbol.get("line_no"), score, "symbol", symbol.get("name"))
                )
        for call in record.get("calls") or []:
            score = _symbol_score(normalized, query_tail, str(call.get("name") or ""))
            if score:
                matches.append(
                    _match(relative, call.get("line_no"), score - 10, "caller", call.get("owner"))
                )
        for interface in record.get("interfaces") or []:
            value = str(interface.get("value") or "")
            if normalized.casefold() == value.casefold():
                matches.append(
                    _match(relative, interface.get("line_no"), 95, "interface", interface.get("owner"))
                )

        relative_text = str(relative)
        if len(normalized) >= 4 and normalized.casefold() in relative_text.casefold():
            matches.append(_match(relative, 1, 45, "file", ""))
        summary = str(record.get("summary") or "")
        if len(normalized) >= 4 and normalized.casefold() in summary.casefold():
            matches.append(_match(relative, 1, 35, "summary", ""))

    matches.sort(key=lambda item: (-int(item["score"]), item["path"], int(item["line_no"])))
    result: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, int, str]] = set()
    for item in matches:
        key = (item["path"], int(item["line_no"]), str(item.get("match_type") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= max(1, max_results):
            break
    return result


def source_file_summary(path: Path, symbols: Iterable[str], calls: Iterable[str]) -> str:
    symbol_values = list(dict.fromkeys(value for value in symbols if value))[:12]
    call_values = list(dict.fromkeys(value for value in calls if value))[:12]
    parts = [f"{path.name} ({path.suffix.lower().lstrip('.') or 'source'})"]
    if symbol_values:
        parts.append("defines " + ", ".join(symbol_values))
    if call_values:
        parts.append("calls " + ", ".join(call_values))
    return "; ".join(parts)


def _index_path(index_root: Path, repository_root: Path) -> Path:
    digest = hashlib.sha256(str(repository_root).encode("utf-8")).hexdigest()[:16]
    name = re.sub(r"[^A-Za-z0-9_.-]+", "-", repository_root.name) or "repository"
    return index_root / f"{name}-{digest}.json"


def _load_index(path: Path, repository_root: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return {}
    if not isinstance(value, dict):
        return {}
    if int(value.get("schema_version") or 0) != INDEX_SCHEMA_VERSION:
        return {}
    if str(value.get("repository_root") or "") != str(repository_root):
        return {}
    return value


def _write_index(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as output:
            json.dump(value, output, ensure_ascii=False, separators=(",", ":"))
            temp_path = Path(output.name)
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


@contextmanager
def _file_lock(index_path: Path):
    index_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = index_path.with_suffix(index_path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _source_paths(root: Path) -> List[Path]:
    result: List[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        relative_parts = path.relative_to(root).parts
        if any(part in IGNORED_DIRECTORIES for part in relative_parts[:-1]):
            continue
        try:
            if path.stat().st_size > MAX_INDEX_FILE_BYTES:
                continue
        except OSError:
            continue
        result.append(path)
    return sorted(result)


def _revision_changed_paths(
    root: Path,
    previous_revision: str,
    revision: str,
    timeout_seconds: float,
) -> Set[str] | None:
    if not previous_revision or not revision or not (root / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", previous_revision, revision, "--"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _workspace_revision(files: Dict[str, Dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, record in sorted(files.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(str(record.get("content_sha256") or "").encode("ascii", errors="ignore"))
    return "workspace-" + digest.hexdigest()[:16]


def _normalize_query(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip(" \t\r\n\"'[](),;")


def _symbol_tail(value: str) -> str:
    return re.split(r"::|->|\.", value)[-1].casefold()


def _symbol_score(query: str, query_tail: str, value: str) -> int:
    if not value:
        return 0
    folded = value.casefold()
    tail = _symbol_tail(value)
    if query.casefold() == folded:
        return 130
    if query_tail == tail:
        return 115
    if len(query) >= 4 and query.casefold() in folded:
        return 75
    return 0


def _match(relative: str, line_no: Any, score: int, match_type: str, owner: Any) -> Dict[str, Any]:
    return {
        "path": relative,
        "line_no": max(1, int(line_no or 1)),
        "score": score,
        "match_type": match_type,
        "owner": str(owner or ""),
    }
