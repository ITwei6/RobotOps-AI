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
    existing_root = _resolve_search_root(repo, roots, module_name)
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
            context = _source_context(match["path"], int(match["line_no"]))
            key = (
                str(match["path"]),
                context["function_name"] or context["snippet"],
            )
            if key in seen:
                continue
            seen.add(key)
            sources.append(
                {
                    "repo": search_root.name,
                    "branch": evidence_branch,
                    "commit": evidence_commit,
                    "file_path": _display_path(search_root, match["path"]),
                    "function_name": context["function_name"],
                    "matched_text": keyword,
                    "snippet": context["snippet"],
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
        if _is_git_repository(local_path, timeout_seconds):
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


def _is_git_repository(path: Path, timeout_seconds: float) -> bool:
    result = _run_git(["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"], timeout_seconds)
    return result.returncode == 0 and result.stdout.strip() == "true"


def _git_error(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or "git command failed").strip()[:512]


def _repo_name(repo: str) -> str:
    name = Path(urlparse(repo).path or repo).name
    return name[:-4] if name.endswith(".git") else name


def _resolve_search_root(repo: str, roots: Iterable[str], module_name: str = "") -> Path | None:
    candidates: List[Path] = []
    if repo:
        candidates.append(Path(repo).expanduser())
    repo_name = _repo_name(repo) if repo else module_name
    for root in roots:
        path = Path(root).expanduser()
        if repo_name:
            if path.name == repo_name:
                candidates.append(path)
            candidates.append(path / repo_name)
        else:
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

    command = [
        "rg",
        "--line-number",
        "--with-filename",
        "--fixed-strings",
        "--no-heading",
        "-m",
        str(max_results),
        keyword,
        str(root),
    ]
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


def _source_context(
    path: Path,
    line_no: int,
    *,
    max_lines: int = 160,
    fallback_context: int = 24,
) -> Dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {"function_name": "", "snippet": ""}
    if not lines:
        return {"function_name": "", "snippet": ""}

    target = max(0, min(line_no - 1, len(lines) - 1))
    scope = _python_function_scope(lines, target) if path.suffix.lower() == ".py" else None
    if scope is None:
        scope = _brace_function_scope(lines, target)

    if scope is not None:
        start, end, function_name = scope
    elif len(lines) <= max_lines:
        start, end, function_name = 0, len(lines) - 1, ""
    else:
        start = max(0, target - fallback_context)
        end = min(len(lines) - 1, target + fallback_context)
        function_name = ""

    snippet = _format_context(lines, start, end, target, max_lines=max_lines)
    return {"function_name": function_name, "snippet": snippet}


def _function_name(path: Path, line_no: int) -> str:
    return _source_context(path, line_no)["function_name"]


def _brace_function_scope(lines: List[str], target: int) -> tuple[int, int, str] | None:
    masked = _mask_non_code(lines)
    pairs = _brace_pairs(masked)
    candidates: List[tuple[int, int, str]] = []
    for open_line, open_column, close_line in pairs:
        if open_line <= target <= close_line:
            signature = _signature_before_brace(masked, open_line, open_column)
            function_name = _callable_name(signature)
            if function_name:
                candidates.append((open_line, close_line, function_name))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])


def _mask_non_code(lines: List[str]) -> List[str]:
    masked: List[str] = []
    in_block_comment = False
    for line in lines:
        output = list(line)
        index = 0
        quote = ""
        while index < len(line):
            if in_block_comment:
                end = line.find("*/", index)
                if end < 0:
                    for position in range(index, len(line)):
                        output[position] = " "
                    index = len(line)
                    continue
                for position in range(index, end + 2):
                    output[position] = " "
                in_block_comment = False
                index = end + 2
                continue

            if quote:
                output[index] = " "
                if line[index] == "\\":
                    if index + 1 < len(line):
                        output[index + 1] = " "
                    index += 2
                    continue
                if line[index] == quote:
                    quote = ""
                index += 1
                continue

            if line.startswith("//", index):
                for position in range(index, len(line)):
                    output[position] = " "
                break
            if line.startswith("/*", index):
                output[index] = output[index + 1] = " "
                in_block_comment = True
                index += 2
                continue
            if line[index] in {'"', "'"}:
                quote = line[index]
                output[index] = " "
            index += 1
        masked.append("".join(output))
    return masked


def _brace_pairs(lines: List[str]) -> List[tuple[int, int, int]]:
    stack: List[tuple[int, int]] = []
    pairs: List[tuple[int, int, int]] = []
    for line_index, line in enumerate(lines):
        for column, character in enumerate(line):
            if character == "{":
                stack.append((line_index, column))
            elif character == "}" and stack:
                open_line, open_column = stack.pop()
                pairs.append((open_line, open_column, line_index))
    for open_line, open_column in stack:
        pairs.append((open_line, open_column, len(lines) - 1))
    return pairs


def _signature_before_brace(lines: List[str], line_index: int, column: int) -> str:
    start = max(0, line_index - 15)
    prefix = "\n".join(lines[start:line_index] + [lines[line_index][:column]])
    boundary = max(prefix.rfind(";"), prefix.rfind("}"), prefix.rfind("{"))
    return re.sub(r"\s+", " ", prefix[boundary + 1 :]).strip()


def _callable_name(signature: str) -> str:
    if "(" not in signature or ")" not in signature:
        return ""
    if re.match(r"^(?:if|for|while|switch|catch)\s*\(", signature):
        return ""
    matches = re.findall(
        r"(?<![\w:])("
        r"(?:[A-Za-z_]\w*::)*(?:~?[A-Za-z_]\w*|operator\s*[^\s(]+)"
        r")\s*\(",
        signature,
    )
    if not matches:
        return ""
    name = matches[-1].strip()
    if name in {"if", "for", "while", "switch", "catch"}:
        return ""
    return name


def _python_function_scope(lines: List[str], target: int) -> tuple[int, int, str] | None:
    for start in range(target, -1, -1):
        match = re.match(r"^(\s*)(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(", lines[start])
        if not match:
            continue
        indent = len(match.group(1).expandtabs(4))
        end = len(lines) - 1
        for index in range(start + 1, len(lines)):
            stripped = lines[index].strip()
            if not stripped:
                continue
            indent_text = lines[index][: len(lines[index]) - len(lines[index].lstrip(" \t"))]
            current_indent = len(indent_text.expandtabs(4))
            if current_indent <= indent and not lines[index].lstrip().startswith("#"):
                end = index - 1
                break
        if target > end:
            continue
        class_name = _enclosing_python_class(lines, start, indent)
        function_name = f"{class_name}.{match.group(2)}" if class_name else match.group(2)
        return start, end, function_name
    return None


def _enclosing_python_class(lines: List[str], function_start: int, function_indent: int) -> str:
    for index in range(function_start - 1, -1, -1):
        match = re.match(r"^(\s*)class\s+([A-Za-z_]\w*)", lines[index])
        if not match:
            continue
        if len(match.group(1).expandtabs(4)) < function_indent:
            return match.group(2)
    return ""


def _format_context(
    lines: List[str],
    start: int,
    end: int,
    target: int,
    *,
    max_lines: int,
) -> str:
    total = end - start + 1
    if total <= max_lines:
        selected = list(range(start, end + 1))
    else:
        edge_size = min(12, max_lines // 6)
        center_size = max_lines - edge_size * 2
        center_start = max(start + edge_size, target - center_size // 2)
        center_end = min(end - edge_size, center_start + center_size - 1)
        center_start = max(start + edge_size, center_end - center_size + 1)
        selected = sorted(
            set(range(start, start + edge_size))
            | set(range(center_start, center_end + 1))
            | set(range(end - edge_size + 1, end + 1))
        )

    output: List[str] = []
    previous = -1
    for index in selected:
        if previous >= 0 and index > previous + 1:
            output.append(f"... lines {previous + 2}-{index} omitted ...")
        output.append(f"{index + 1}: {lines[index]}")
        previous = index
    return "\n".join(output)


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
