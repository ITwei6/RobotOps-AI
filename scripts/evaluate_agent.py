#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent_service.evaluation import evaluate_cases, load_evaluation_cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the offline RobotOps Agent evaluation set.")
    parser.add_argument(
        "--cases",
        default=str(PROJECT_ROOT / "agent_service/evaluation_cases.json"),
        help="Path to an evaluation case JSON file.",
    )
    args = parser.parse_args()

    # Evaluation must be reproducible and must not call an external model.
    os.environ["ROBOTOPS_LLM_ENABLED"] = "false"
    os.environ["DEEPSEEK_API_KEY"] = ""
    os.environ["ROBOTOPS_AGENT_MAX_TOOL_ITERATIONS"] = "0"
    result = evaluate_cases(load_evaluation_cases(args.cases))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed_cases"] == result["total_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
