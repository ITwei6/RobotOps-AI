import unittest
from unittest.mock import patch

from agent_service.app.workflow import run_diagnosis_workflow


class DiagnosisWorkflowTest(unittest.TestCase):
    def test_workflow_uses_rule_fallback_without_llm_key(self):
        report = run_diagnosis_workflow(
            {
                "bug": {
                    "bug_id": "bug-000001",
                    "title": "触摸后机器人没有反应",
                    "description": "T 型机器人拍触摸板没反应",
                    "robot_type": "ROBOT_TYPE_T",
                    "main_module": "interaction",
                    "occurred_time": 1785396730000,
                    "source_repo": "/home/dev/workspace/interaction",
                    "branch": "main",
                },
                "logs": [
                    {
                        "module_name": "interaction",
                        "file_name": "interaction.log",
                        "line_no": 3,
                        "log_time": 1785396730150,
                        "log_level": "warn",
                        "message": "Current action is DAMPING_DEFAULT or PASSIVE_DEFAULT, ignore touch trigger, action_id: 100",
                        "raw_line": "2026-07-30 15:32:10.150 WARN Current action is DAMPING_DEFAULT or PASSIVE_DEFAULT, ignore touch trigger, action_id: 100",
                    }
                ],
            }
        )

        self.assertEqual(report["suspected_module"], "interaction")
        self.assertEqual(report["agent_version"], "langgraph-diagnosis-v1")
        self.assertGreaterEqual(report["confidence"], 0.8)
        self.assertIn("T1Checker::CheckTouch", report["evidence_sources"][0]["function_name"])

    def test_workflow_keeps_low_confidence_without_evidence(self):
        report = run_diagnosis_workflow(
            {
                "bug": {
                    "title": "机器人没有反应",
                    "description": "没有日志",
                    "robot_type": "ROBOT_TYPE_T",
                    "main_module": "interaction",
                    "occurred_time": 1785396730000,
                },
                "logs": [],
            }
        )

        self.assertLess(report["confidence"], 0.3)
        self.assertTrue(report["questions_for_human"])

    @patch("agent_service.app.workflow.nodes.search_source")
    @patch("agent_service.app.workflow.nodes.fetch_log_context")
    def test_workflow_collects_log_and_source_evidence_with_tools(self, fetch_log_context, search_source):
        fetch_log_context.return_value = {
            "ok": True,
            "logs": [
                {
                    "module_name": "interaction",
                    "file_name": "interaction.log",
                    "line_no": 42,
                    "log_time": 1785396730150,
                    "log_level": "warn",
                    "message": "Current action is DAMPING_DEFAULT or PASSIVE_DEFAULT, ignore touch trigger",
                    "raw_line": "2026-07-30 15:32:10.150 WARN Current action is DAMPING_DEFAULT or PASSIVE_DEFAULT, ignore touch trigger",
                }
            ],
        }
        search_source.return_value = {
            "ok": True,
            "sources": [
                {
                    "repo": "interaction",
                    "file_path": "interaction/src/scheduler/checker/t1_checker.cpp",
                    "function_name": "T1Checker::CheckTouch",
                    "matched_text": "ignore touch trigger",
                    "snippet": "return false;",
                }
            ],
        }

        report = run_diagnosis_workflow(
            {
                "bug": {
                    "bug_id": "bug-000002",
                    "title": "触摸后机器人没有反应",
                    "description": "T 型机器人拍触摸板没反应",
                    "robot_type": "ROBOT_TYPE_T",
                    "main_module": "interaction",
                    "occurred_time": 1785396730000,
                    "log_package_id": "pkg-20260730",
                    "source_repo": "interaction",
                },
                "logs": [],
            }
        )

        self.assertEqual(report["suspected_module"], "interaction")
        self.assertGreaterEqual(report["confidence"], 0.8)
        self.assertEqual(report["evidence_logs"][0]["line_no"], 42)
        self.assertIn("T1Checker::CheckTouch", report["evidence_sources"][0]["function_name"])
        fetch_log_context.assert_called_once()
        search_source.assert_called_once()


if __name__ == "__main__":
    unittest.main()
