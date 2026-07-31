import unittest

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


if __name__ == "__main__":
    unittest.main()
