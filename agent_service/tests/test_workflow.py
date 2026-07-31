import json
import tempfile
import unittest
from pathlib import Path
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
        self.assertIn("T1 CheckTouch 前置检查拦截", report["execution_chain"])
        self.assertEqual(report["evidence_sources"], [])

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
        self.assertEqual(fetch_log_context.call_args.kwargs["args"]["module_name"], "")
        search_source.assert_called_once()

    @patch("agent_service.app.workflow.nodes.search_source")
    @patch("agent_service.app.workflow.nodes.fetch_log_context")
    def test_workflow_searches_source_for_each_observed_module(self, fetch_log_context, search_source):
        fetch_log_context.return_value = {
            "ok": True,
            "logs": [
                {
                    "module_name": "interaction",
                    "file_name": "interaction.log",
                    "line_no": 10,
                    "log_level": "error",
                    "message": "interaction request failed",
                },
                {
                    "module_name": "mc",
                    "file_name": "mc.log",
                    "line_no": 20,
                    "log_level": "error",
                    "message": "mc action failed",
                },
            ],
        }

        def source_result(*, args, **_kwargs):
            module = args["module_name"]
            return {
                "ok": True,
                "sources": [
                    {
                        "repo": module,
                        "file_path": f"{module}/src/failure.cpp",
                        "function_name": f"{module}::HandleFailure",
                        "matched_text": "failed",
                        "snippet": "calls mc SetMcAction" if module == "interaction" else "return false;",
                    }
                ],
            }

        search_source.side_effect = source_result
        report = run_diagnosis_workflow(
            {
                "bug": {
                    "bug_id": "bug-multi-module",
                    "title": "机器人动作失败",
                    "description": "interaction 请求失败，同时 mc 返回动作失败",
                    "robot_type": "ROBOT_TYPE_T",
                    "main_module": "interaction",
                    "occurred_time": 1785396730000,
                    "log_package_id": "pkg-multi-module",
                },
                "logs": [],
            }
        )

        searched_modules = {call.kwargs["args"]["module_name"] for call in search_source.call_args_list}
        self.assertEqual(searched_modules, {"interaction", "mc"})
        self.assertEqual(search_source.call_args_list[0].kwargs["args"]["module_name"], "interaction")
        self.assertEqual(
            {source["repo"] for source in report["evidence_sources"]},
            {"interaction", "mc"},
        )

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
        self.assertIn("未进入触摸任务创建/派发阶段", report["execution_chain"])
        self.assertEqual(report["evidence_sources"], [])
        self.assertGreaterEqual(report["confidence"], 0.85)
        generate_structured_report.assert_called_once()

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key", "ROBOTOPS_LLM_ENABLED": "true"})
    @patch("agent_service.app.workflow.nodes.generate_structured_report")
    def test_workflow_falls_back_when_llm_fails(self, generate_structured_report):
        generate_structured_report.side_effect = DeepSeekUnavailable("mock llm failure")

        report = run_diagnosis_workflow(self.touch_payload)

        self.assertEqual(report["suspected_module"], "interaction")
        self.assertEqual(report["agent_version"], "langgraph-diagnosis-v1")
        self.assertLessEqual(report["confidence"], 0.75)
        self.assertEqual(report["evidence_sources"], [])
        generate_structured_report.assert_called_once()

    def test_workflow_adds_historical_case_as_reference(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "cases.json").write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "case_id": "case-touch-001",
                                "title": "T 型触摸后没有反应",
                                "robot_type": "ROBOT_TYPE_T",
                                "main_module": "interaction",
                                "causes": ["历史上由 CheckTouch 拦截"],
                                "actions": ["核对 MC action"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"ROBOTOPS_CASE_SEARCH_ROOTS": tmpdir}):
                report = run_diagnosis_workflow(self.touch_payload)

        self.assertTrue(any("case-touch-001" in item for item in report["possible_causes"]))
        self.assertTrue(any("case-touch-001" in item for item in report["recommended_actions"]))

    def test_workflow_adds_knowledge_as_source_reference(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "knowledge.json").write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "source_id": "sop-interaction-001",
                                "main_module": "interaction",
                                "title": "触摸排查 SOP",
                                "content": "检查 self check 与 MC action。",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch.dict(
                "os.environ",
                {
                    "ROBOTOPS_CASE_SEARCH_ROOTS": "/path/that/does/not/exist",
                    "ROBOTOPS_KNOWLEDGE_SEARCH_ROOTS": tmpdir,
                },
            ):
                report = run_diagnosis_workflow(self.touch_payload)

        self.assertTrue(any("sop-interaction-001" in item for item in report["recommended_actions"]))


if __name__ == "__main__":
    unittest.main()
