import unittest
from unittest.mock import patch

from agent_service.app.llm.deepseek import DeepSeekUnavailable
from agent_service.app.workflow import run_diagnosis_workflow


class DiagnosisWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.touch_payload = {
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

    def test_workflow_uses_rule_fallback_without_llm_key(self):
        report = run_diagnosis_workflow(self.touch_payload)

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

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key", "ROBOTOPS_LLM_ENABLED": "true"})
    @patch("agent_service.app.workflow.nodes.generate_structured_report")
    def test_workflow_merges_llm_report_with_rule_evidence(self, generate_structured_report):
        generate_structured_report.return_value = {
            "summary": "LLM 结合规则 baseline 判断为 interaction touch 前置检查拦截。",
            "suspected_module": "interaction",
            "possible_causes": ["LLM cause"],
            "evidence_logs": [],
            "evidence_sources": [],
            "recommended_actions": ["LLM action"],
            "confidence": 0.91,
            "questions_for_human": [],
            "agent_version": "llm-test",
            "status": "TASK_STATUS_SUCCEEDED",
        }

        report = run_diagnosis_workflow(self.touch_payload)

        self.assertEqual(report["agent_version"], "langgraph-diagnosis-v1")
        self.assertIn("LLM", report["summary"])
        self.assertEqual(report["evidence_logs"][0]["line_no"], 3)
        self.assertIn("T1Checker::CheckTouch", report["evidence_sources"][0]["function_name"])
        self.assertGreaterEqual(report["confidence"], 0.9)
        generate_structured_report.assert_called_once()

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key", "ROBOTOPS_LLM_ENABLED": "true"})
    @patch("agent_service.app.workflow.nodes.generate_structured_report")
    def test_workflow_falls_back_when_llm_fails(self, generate_structured_report):
        generate_structured_report.side_effect = DeepSeekUnavailable("mock llm failure")

        report = run_diagnosis_workflow(self.touch_payload)

        self.assertEqual(report["suspected_module"], "interaction")
        self.assertEqual(report["agent_version"], "langgraph-diagnosis-v1")
        self.assertLessEqual(report["confidence"], 0.75)
        self.assertIn("T1Checker::CheckTouch", report["evidence_sources"][0]["function_name"])
        generate_structured_report.assert_called_once()


if __name__ == "__main__":
    unittest.main()
