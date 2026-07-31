from __future__ import annotations

import re
import shutil
import subprocess
from urllib.parse import urlparse
from pathlib import Path
from typing import Any, Dict, Iterable, List


def search_source(
    *,
    roots: Iterable[str],
    timeout_seconds: float,
    args: Dict[str, Any],
    workspace_root: str = ".robotops/source-cache",
    repositories: Dict[str, Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    module_name = str(args.get("module_name") or args.get("main_module") or "").strip()
    repository = dict((repositories or {}).get(module_name) or {})
    repo = str(repository.get("local_path") or repository.get("repo_url") or args.get("repo") or "")
    branch = str(args.get("branch") or repository.get("branch") or "")
    commit = str(args.get("commit") or repository.get("commit") or "")
    existing_root = _resolve_search_root(repo, roots)
    sync_repo = str(existing_root) if existing_root is not None else repo
    sync_result = sync_source_repo(
        repo=sync_repo,
        workspace_root=workspace_root,
        branch=branch,
        commit=commit,
        timeout_seconds=timeout_seconds,
    )
    if not sync_result["ok"]:
        return {"ok": False, "sources": [], "error": sync_result["error"], "source_sync": sync_result}

    search_root = Path(sync_result["local_path"]) if sync_result.get("local_path") else existing_root
    if search_root is None:
        return {"ok": False, "sources": [], "error": "source repo not found", "source_sync": sync_result}

    keywords = _keywords(args.get("keywords") or [])
    if not keywords:
        return {"ok": False, "sources": [], "error": "source keywords are empty", "source_sync": sync_result}

    max_results = max(1, min(_int_value(args.get("max_results"), 10), 50))
    evidence_branch = branch
    evidence_commit = commit or str(sync_result.get("revision") or "")
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
                    "branch": evidence_branch,
                    "commit": evidence_commit,
                    "file_path": _display_path(search_root, match["path"]),
                    "function_name": _function_name(match["path"], int(match["line_no"])),
                    "matched_text": keyword,
                    "snippet": snippet,
                }
            )
            if len(sources) >= max_results:
                return {"ok": True, "sources": sources, "source_sync": sync_result}

    return {"ok": True, "sources": sources, "source_sync": sync_result}


def sync_source_repo(
    *,
    repo: str,
    workspace_root: str,
    branch: str,
    commit: str,
    timeout_seconds: float,
) -> Dict[str, Any]:
    """Ensure a source repository is available locally before searching it."""
    if not repo:
        return {"ok": False, "action": "none", "local_path": "", "error": "source repo is empty"}

    requested = Path(repo).expanduser()
    if requested.exists() and requested.is_dir():
        local_path = requested.resolve()
        if (local_path / ".git").exists():
            return _pull_existing_repo(local_path, branch, commit, timeout_seconds)
        return {"ok": True, "action": "use_local", "local_path": str(local_path), "revision": ""}

    parsed = urlparse(repo)
    if parsed.scheme not in {"http", "https", "ssh", "git"} and not repo.endswith(".git"):
        return {"ok": False, "action": "none", "local_path": "", "error": f"source repo path not found: {repo}"}

    root = Path(workspace_root).expanduser()
    target = root / _repo_name(repo)
    root.mkdir(parents=True, exist_ok=True)
    if (target / ".git").exists():
        return _pull_existing_repo(target, branch, commit, timeout_seconds)

    command = ["git", "clone"]
    if branch:
        command.extend(["--branch", branch])
    command.extend([repo, str(target)])
    result = _run_git(command, timeout_seconds)
    if result.returncode != 0:
        return {"ok": False, "action": "clone", "local_path": str(target), "error": _git_error(result)}
    checkout = _checkout_revision(target, commit, timeout_seconds)
    if not checkout["ok"]:
        return checkout
    return {"ok": True, "action": "clone", "local_path": str(target), "revision": checkout["revision"]}


def _pull_existing_repo(path: Path, branch: str, commit: str, timeout_seconds: float) -> Dict[str, Any]:
    if branch:
        checkout_branch = _run_git(["git", "-C", str(path), "checkout", branch], timeout_seconds)
        if checkout_branch.returncode != 0:
            return {"ok": False, "action": "checkout", "local_path": str(path), "error": _git_error(checkout_branch)}
    pull = _run_git(["git", "-C", str(path), "pull", "--ff-only"], timeout_seconds)
    if pull.returncode != 0:
        return {"ok": False, "action": "pull", "local_path": str(path), "error": _git_error(pull)}
    checkout = _checkout_revision(path, commit, timeout_seconds)
    if not checkout["ok"]:
        return checkout
    return {"ok": True, "action": "pull", "local_path": str(path), "revision": checkout["revision"]}


def _checkout_revision(path: Path, commit: str, timeout_seconds: float) -> Dict[str, Any]:
    if commit:
        checkout = _run_git(["git", "-C", str(path), "checkout", "--detach", commit], timeout_seconds)
        if checkout.returncode != 0:
            return {"ok": False, "action": "checkout", "local_path": str(path), "error": _git_error(checkout)}
    revision = _run_git(["git", "-C", str(path), "rev-parse", "HEAD"], timeout_seconds)
    return {
        "ok": revision.returncode == 0,
        "action": "checkout" if commit else "use_local",
        "local_path": str(path),
        "revision": revision.stdout.strip(),
        "error": _git_error(revision) if revision.returncode != 0 else "",
    }


def _run_git(command: List[str], timeout_seconds: float) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout_seconds)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(command, 1, "", str(exc))


def _git_error(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or "git command failed").strip()[:512]


def _repo_name(repo: str) -> str:
    name = Path(urlparse(repo).path or repo).name
    return name[:-4] if name.endswith(".git") else name


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

    # Prefer an actual qualified method definition. Calls inside the matched
    # line, such as StateManager::GetInstance(), must not shadow the owner.
    for idx in range(min(line_no - 1, len(lines) - 1), max(-1, line_no - 80), -1):
        text = lines[idx].strip()
        match = re.search(
            r"\b([A-Za-z_]\w*(?:::[A-Za-z_]\w*)+)\s*\([^;]*\)\s*(?:const\s*)?\{",
            text,
        )
        if match and not text.startswith(("if ", "for ", "while ", "switch ")):
            return match.group(1)

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
            and not re.fullmatch(r"[A-Z][A-Z0-9_]*", match.group(1))
        ):
            return match.group(1)
    return ""


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
