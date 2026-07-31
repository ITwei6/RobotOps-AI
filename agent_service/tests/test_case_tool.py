import json
import tempfile
import unittest
from pathlib import Path

from agent_service.app.tools.case_tool import search_cases


class CaseToolTest(unittest.TestCase):
    def test_search_cases_scores_robot_module_and_keywords(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            case_path = Path(tmpdir) / "cases.json"
            case_path.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "case_id": "case-touch-001",
                                "title": "T 型触摸后没有反应",
                                "robot_type": "ROBOT_TYPE_T",
                                "main_module": "interaction",
                                "causes": ["CheckTouch 拦截"],
                                "actions": ["检查 MC action"],
                            },
                            {"case_id": "case-other", "title": "Q 型移动超时", "main_module": "mc"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result = search_cases(
                (tmpdir,),
                {
                    "title": "触摸后没有反应",
                    "robot_type": "ROBOT_TYPE_T",
                    "main_module": "interaction",
                    "keywords": ["CheckTouch"],
                    "max_results": 5,
                },
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["history_cases"][0]["case_id"], "case-touch-001")
        self.assertGreater(result["history_cases"][0]["match_score"], 0.5)

    def test_missing_case_root_is_a_valid_empty_result(self):
        result = search_cases(("/path/that/does/not/exist",), {"title": "unknown"})
        self.assertEqual(result, {"ok": True, "history_cases": []})


if __name__ == "__main__":
    unittest.main()
