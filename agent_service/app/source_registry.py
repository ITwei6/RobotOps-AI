from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_repositories(path: str) -> Dict[str, Dict[str, Any]]:
    registry_path = Path(path).expanduser()
    if not registry_path.exists():
        return {}
    try:
        value = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return {}
    repositories = value.get("repositories", value) if isinstance(value, dict) else {}
    return {
        str(module): dict(config)
        for module, config in repositories.items()
        if isinstance(config, dict) and str(module).strip()
    }


def save_repository(path: str, module_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    registry_path = Path(path).expanduser()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    repositories = load_repositories(path)
    repositories[module_name] = dict(config)
    temp_path = registry_path.with_suffix(registry_path.suffix + ".tmp")
    temp_path.write_text(json.dumps({"repositories": repositories}, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(registry_path)
    return repositories[module_name]
