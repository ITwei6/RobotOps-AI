from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List


def search_source(*, roots: Iterable[str], timeout_seconds: float, args: Dict[str, Any]) -> Dict[str, Any]:
    search_root = _resolve_search_root(str(args.get("repo") or ""), roots)
    if search_root is None:
        return {"ok": False, "sources": [], "error": "source repo not found"}

    keywords = _keywords(args.get("keywords") or [])
    if not keywords:
        return {"ok": False, "sources": [], "error": "source keywords are empty"}

    max_results = max(1, min(_int_value(args.get("max_results"), 10), 50))
    branch = str(args.get("branch") or "")
    commit = str(args.get("commit") or "")
    sources: List[Dict[str, Any]] = []
    seen = set()

    for keyword in keywords:
        matches = _run_rg(search_root, keyword, max_results=max_results, timeout_seconds=timeout_seconds)
        for match in matches:
            key = (str(match["path"]), int(match["line_no"]), keyword)
            if key in seen:
                continue
            seen.add(key)
            snippet = _snippet(match["path"], int(match["line_no"]))
            sources.append(
                {
                    "repo": search_root.name,
                    "branch": branch,
                    "commit": commit,
                    "file_path": _display_path(search_root, match["path"]),
                    "function_name": _function_name(match["path"], int(match["line_no"])),
                    "matched_text": keyword,
                    "snippet": snippet,
                }
            )
            if len(sources) >= max_results:
                return {"ok": True, "sources": sources}

    return {"ok": True, "sources": sources}


def _resolve_search_root(repo: str, roots: Iterable[str]) -> Path | None:
    candidates: List[Path] = []
    if repo:
        candidates.append(Path(repo).expanduser())
    repo_name = Path(repo).name if repo else ""
    for root in roots:
        path = Path(root).expanduser()
        if repo_name:
            candidates.append(path / repo_name)
        candidates.append(path)

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists() and resolved.is_dir():
            return resolved
    return None


def _keywords(values: List[Any]) -> List[str]:
    result: List[str] = []
    for value in values:
        keyword = str(value).strip()
        if not keyword:
            continue
        if len(keyword) > 160:
            keyword = keyword[:160]
        if keyword not in result:
            result.append(keyword)
    return result[:8]


def _run_rg(root: Path, keyword: str, *, max_results: int, timeout_seconds: float) -> List[Dict[str, Any]]:
    if shutil.which("rg") is None:
        return _run_plain_text_search(root, keyword, max_results=max_results)

    command = ["rg", "--line-number", "--fixed-strings", "--no-heading", "-m", str(max_results), keyword, str(root)]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return _run_plain_text_search(root, keyword, max_results=max_results)

    matches: List[Dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parsed = _parse_rg_line(line)
        if parsed:
            matches.append(parsed)
    return matches


def _run_plain_text_search(root: Path, keyword: str, *, max_results: int) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for path in root.rglob("*"):
        if len(matches) >= max_results:
            break
        if not path.is_file() or _skip_path(path):
            continue
        try:
            with path.open("r", encoding="utf-8", errors="replace") as source:
                for line_no, line in enumerate(source, start=1):
                    if keyword in line:
                        matches.append({"path": path, "line_no": line_no, "content": line.rstrip("\n")})
                        if len(matches) >= max_results:
                            break
        except OSError:
            continue
    return matches


def _skip_path(path: Path) -> bool:
    ignored_parts = {".git", "build", "cmake-build-debug", "cmake-build-release", "__pycache__"}
    if any(part in ignored_parts for part in path.parts):
        return True
    return path.suffix.lower() in {".o", ".a", ".so", ".dll", ".exe", ".png", ".jpg", ".jpeg", ".zip", ".gz"}


def _parse_rg_line(line: str) -> Dict[str, Any] | None:
    parts = line.split(":", 2)
    if len(parts) != 3:
        return None
    path_text, line_no_text, content = parts
    try:
        line_no = int(line_no_text)
    except ValueError:
        return None
    return {"path": Path(path_text), "line_no": line_no, "content": content}


def _display_path(root: Path, path: Path) -> str:
    try:
        relative = path.resolve().relative_to(root)
        return f"{root.name}/{relative.as_posix()}"
    except ValueError:
        return path.as_posix()


def _snippet(path: Path, line_no: int, context: int = 3) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    start = max(1, line_no - context)
    end = min(len(lines), line_no + context)
    return "\n".join(f"{idx}: {lines[idx - 1]}" for idx in range(start, end + 1))


def _function_name(path: Path, line_no: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""

    signature = ""
    for idx in range(min(line_no - 1, len(lines) - 1), max(-1, line_no - 80), -1):
        text = lines[idx].strip()
        if not text or text.startswith("//"):
            continue
        signature = f"{text} {signature}".strip()
        match = re.search(r"([A-Za-z_]\w*(?:::[A-Za-z_]\w*)+)\s*\(", signature)
        if match:
            return match.group(1)
        match = re.search(r"\b([A-Za-z_]\w*)\s*\([^;]*\)\s*(?:const\s*)?\{?", signature)
        if (
            match
            and "{" in signature
            and "<<" not in signature
            and not signature.startswith(("if ", "for ", "while ", "switch ", "return "))
        ):
            return match.group(1)
    return ""


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
