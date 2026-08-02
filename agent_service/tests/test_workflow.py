import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_service.app.llm.deepseek import DeepSeekUnavailable
from agent_service.app.workflow import run_diagnosis_workflow
from agent_service.app.workflow.nodes import _correlation_values, _mentions_module


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

    @patch(
        "agent_service.app.workflow.nodes.search_source",
        return_value={"ok": True, "sources": []},
    )
    def test_workflow_uses_rule_fallback_without_llm_key(self, search_source):
        report = run_diagnosis_workflow(self.touch_payload)

        self.assertEqual(report["suspected_module"], "interaction")
        self.assertEqual(report["agent_version"], "langgraph-diagnosis-v3")
        self.assertEqual(report["generation_mode"], "deterministic_fallback")
        self.assertGreaterEqual(report["confidence"], 0.8)
        self.assertIn("T1 CheckTouch 前置检查拦截", report["execution_chain"])
        self.assertEqual(report["evidence_sources"], [])
        search_source.assert_called_once()

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

    def test_module_reference_matching_handles_short_and_compound_names(self):
        self.assertTrue(_mentions_module("SetMcAction returned false", "mc"))
        self.assertTrue(_mentions_module("HalCameraClient timeout", "hal_camera"))
        self.assertFalse(_mentions_module("cmake configuration failed", "mc"))

    def test_correlation_parser_ignores_non_identifier_state_fields(self):
        values = _correlation_values(
            {
                "module_name": "scheduler",
                "message": "invalid_state: blocked, command_id: cmd-8871",
            }
        )

        self.assertIn("cmd-8871", values)
        self.assertFalse(any("blocked" in value for value in values))

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
                    "log_time": 1785396730000,
                    "log_level": "error",
                    "message": "interaction calls mc SetMcAction and request failed",
                },
                {
                    "module_name": "mc",
                    "file_name": "mc.log",
                    "line_no": 20,
                    "log_time": 1785396730020,
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
        self.assertEqual(report["module_relations"][0]["from_module"], "interaction")
        self.assertEqual(report["module_relations"][0]["to_module"], "mc")
        self.assertEqual(report["module_relations"][0]["evidence_type"], "source")
        self.assertEqual(report["module_relations"][0]["time_delta_ms"], 20)
        self.assertEqual(report["module_relations"][0]["source_log_ref"], "interaction.log:10")
        self.assertEqual(report["module_relations"][0]["target_log_ref"], "mc.log:20")

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key", "ROBOTOPS_LLM_ENABLED": "true"})
    @patch(
        "agent_service.app.workflow.nodes.search_source",
        return_value={"ok": True, "sources": []},
    )
    @patch("agent_service.app.workflow.nodes.generate_structured_report")
    def test_workflow_merges_llm_report_with_rule_evidence(
        self,
        generate_structured_report,
        search_source,
    ):
        generate_structured_report.return_value = {
            "summary": "LLM 结合规则 baseline 判断为 interaction touch 前置检查拦截。",
            "suspected_module": "interaction",
            "possible_causes": ["LLM cause"],
            "evidence_logs": [],
            "evidence_sources": [],
            "recommended_actions": ["LLM action"],
            "confidence": 0.91,
            "questions_for_human": [],
            "module_relations": [
                {
                    "from": "agent",
                    "to": "interaction",
                    "description": "unsupported relation without evidence",
                    "evidence_refs": [],
                }
            ],
            "agent_version": "llm-test",
            "status": "TASK_STATUS_SUCCEEDED",
        }

        payload = json.loads(json.dumps(self.touch_payload))
        payload["logs"][0]["message"] += ", mc state observed"
        payload["logs"].append(
            {
                "module_name": "mc",
                "file_name": "mc.log",
                "line_no": 20,
                "log_time": 1785396730170,
                "log_level": "info",
                "message": "mc action remains PASSIVE_DEFAULT",
                "raw_line": "mc action remains PASSIVE_DEFAULT",
            }
        )
        report = run_diagnosis_workflow(payload)

        self.assertEqual(report["agent_version"], "langgraph-diagnosis-v3")
        self.assertEqual(report["generation_mode"], "deepseek")
        self.assertIn("deepseek-v4-flash", report["generation_detail"])
        self.assertIn("LLM", report["summary"])
        self.assertEqual(report["evidence_logs"][0]["line_no"], 3)
        self.assertIn("未进入触摸任务创建/派发阶段", report["execution_chain"])
        self.assertEqual(report["evidence_sources"], [])
        self.assertGreaterEqual(report["confidence"], 0.85)
        self.assertEqual(report["module_relations"][0]["from_module"], "interaction")
        self.assertEqual(report["module_relations"][0]["to_module"], "mc")
        self.assertEqual(len(report["module_relations"]), 1)
        self.assertEqual(report["module_relations"][0]["time_delta_ms"], 20)
        generate_structured_report.assert_called_once()
        self.assertEqual(
            {call.kwargs["args"]["module_name"] for call in search_source.call_args_list},
            {"interaction", "mc"},
        )

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key", "ROBOTOPS_LLM_ENABLED": "true"})
    @patch(
        "agent_service.app.workflow.nodes.search_source",
        return_value={"ok": True, "sources": []},
    )
    @patch("agent_service.app.workflow.nodes.generate_structured_report")
    def test_workflow_falls_back_when_llm_fails(
        self,
        generate_structured_report,
        search_source,
    ):
        generate_structured_report.side_effect = DeepSeekUnavailable("mock llm failure")

        report = run_diagnosis_workflow(self.touch_payload)

        self.assertEqual(report["suspected_module"], "interaction")
        self.assertEqual(report["agent_version"], "langgraph-diagnosis-v3")
        self.assertEqual(report["generation_mode"], "llm_fallback")
        self.assertIn("deterministic report", report["generation_detail"])
        self.assertLessEqual(report["confidence"], 0.75)
        self.assertEqual(report["evidence_sources"], [])
        generate_structured_report.assert_called_once()
        search_source.assert_called_once()

    @patch("agent_service.app.workflow.nodes.search_source")
    def test_workflow_follows_generic_cross_module_correlation_id(self, search_source):
        def source_result(*, args, **_kwargs):
            module = args["module_name"]
            return {
                "ok": True,
                "sources": [
                    {
                        "repo": module,
                        "file_path": f"{module}/src/handler.cpp",
                        "function_name": f"{module.title()}Handler::Run",
                        "matched_text": args["keywords"][0],
                        "snippet": f"bool {module.title()}Handler::Run() {{ return false; }}",
                    }
                ],
            }

        search_source.side_effect = source_result
        report = run_diagnosis_workflow(
            {
                "bug": {
                    "bug_id": "bug-generic-correlation",
                    "title": "Command execution failed",
                    "description": "A command crosses two modules and is rejected",
                    "robot_type": "ROBOT_TYPE_T",
                    "main_module": "scheduler",
                    "occurred_time": 1785396730000,
                },
                "logs": [
                    {
                        "module_name": "scheduler",
                        "file_name": "scheduler.log",
                        "line_no": 11,
                        "log_time": 1785396730010,
                        "log_level": "ERROR",
                        "message": "Dispatch command failed, command_id: cmd-8871",
                    },
                    {
                        "module_name": "motor_bridge",
                        "file_name": "motor_bridge.log",
                        "line_no": 29,
                        "log_time": 1785396730030,
                        "log_level": "WARN",
                        "message": "Command rejected, command_id: cmd-8871",
                    },
                ],
            }
        )

        searched_modules = [
            call.kwargs["args"]["module_name"]
            for call in search_source.call_args_list
        ]
        self.assertEqual(searched_modules[:2], ["scheduler", "motor_bridge"])
        self.assertFalse(
            any("path_hints" in call.kwargs["args"] for call in search_source.call_args_list)
        )
        relation = next(
            item
            for item in report["module_relations"]
            if item["to_module"] == "motor_bridge"
        )
        self.assertIn("关联标识", relation["reason"])
        self.assertEqual(relation["time_delta_ms"], 20)

    @patch("agent_service.app.workflow.nodes.search_source")
    def test_workflow_iterates_unknown_source_chain_without_fixed_rules(self, search_source):
        def source_result(*, args, **_kwargs):
            query = args["keywords"][0]
            if query == "WorkerPool::Submit":
                source = {
                    "repo": "scheduler",
                    "file_path": "scheduler/src/worker_pool.cpp",
                    "function_name": "WorkerPool::Submit",
                    "matched_text": query,
                    "snippet": "bool WorkerPool::Submit(Task task) { return queue_->Enqueue(task); }",
                }
            elif query == "Enqueue":
                source = {
                    "repo": "scheduler",
                    "file_path": "scheduler/src/queue.cpp",
                    "function_name": "TaskQueue::Enqueue",
                    "matched_text": query,
                    "snippet": "bool TaskQueue::Enqueue(Task task) { return task.ready; }",
                }
            else:
                source = {
                    "repo": "scheduler",
                    "file_path": "scheduler/src/handler.cpp",
                    "function_name": "Scheduler::HandleRequest",
                    "matched_text": "dispatch pipeline failed",
                    "snippet": (
                        "bool Scheduler::HandleRequest(Request request) { "
                        "if (!ValidateRequest(request)) { return false; } "
                        "return WorkerPool::Submit(request); }"
                    ),
                }
            return {
                "ok": True,
                "sources": [source],
                "source_index": {
                    "ok": True,
                    "enabled": True,
                    "action": "reused",
                    "search_strategy": "source_index",
                },
            }

        search_source.side_effect = source_result
        report = run_diagnosis_workflow(
            {
                "bug": {
                    "bug_id": "bug-unknown-source-chain",
                    "title": "dispatch pipeline failed",
                    "description": "A new scheduler bug without a predefined rule",
                    "robot_type": "ROBOT_TYPE_T",
                    "main_module": "scheduler",
                    "occurred_time": 1785396730000,
                },
                "logs": [
                    {
                        "module_name": "scheduler",
                        "file_name": "scheduler.log",
                        "line_no": 8,
                        "log_time": 1785396730010,
                        "log_level": "ERROR",
                        "message": "dispatch pipeline failed",
                    }
                ],
            }
        )

        source_calls = search_source.call_args_list
        self.assertEqual(len(source_calls), 3)
        self.assertIn("dispatch pipeline failed", source_calls[0].kwargs["args"]["keywords"])
        self.assertEqual(source_calls[1].kwargs["args"]["keywords"], ["WorkerPool::Submit"])
        self.assertEqual(source_calls[2].kwargs["args"]["keywords"], ["Enqueue"])
        self.assertEqual(
            {source["function_name"] for source in report["evidence_sources"]},
            {"Scheduler::HandleRequest", "WorkerPool::Submit", "TaskQueue::Enqueue"},
        )
        self.assertIn("source index=source_index, refresh=reused", report["generation_detail"])

    @patch.dict(
        "os.environ",
        {
            "DEEPSEEK_API_KEY": "",
            "ROBOTOPS_LLM_ENABLED": "false",
            "ROBOTOPS_AGENT_MAX_SOURCE_ANALYSIS_ITERATIONS": "1",
        },
    )
    @patch("agent_service.app.workflow.nodes.search_source")
    def test_workflow_limits_iterative_source_analysis(self, search_source):
        def source_result(*, args, **_kwargs):
            query = args["keywords"][0]
            if query == "NextStep":
                source = {
                    "repo": "scheduler",
                    "file_path": "scheduler/src/next_step.cpp",
                    "function_name": "NextStep",
                    "matched_text": query,
                    "snippet": "bool NextStep(Request request) { return FinalStep(request); }",
                }
            else:
                source = {
                    "repo": "scheduler",
                    "file_path": "scheduler/src/handler.cpp",
                    "function_name": "Scheduler::HandleRequest",
                    "matched_text": "dispatch pipeline failed",
                    "snippet": (
                        "bool Scheduler::HandleRequest(Request request) { "
                        "return NextStep(request); }"
                    ),
                }
            return {"ok": True, "sources": [source]}

        search_source.side_effect = source_result
        report = run_diagnosis_workflow(
            {
                "bug": {
                    "bug_id": "bug-source-limit",
                    "title": "dispatch pipeline failed",
                    "description": "A scheduler request stopped in a new pipeline",
                    "robot_type": "ROBOT_TYPE_T",
                    "main_module": "scheduler",
                    "occurred_time": 1785396730000,
                },
                "logs": [
                    {
                        "module_name": "scheduler",
                        "file_name": "scheduler.log",
                        "line_no": 8,
                        "log_time": 1785396730010,
                        "log_level": "ERROR",
                        "message": "dispatch pipeline failed",
                    }
                ],
            }
        )

        self.assertEqual(search_source.call_count, 2)
        self.assertEqual(search_source.call_args_list[1].kwargs["args"]["keywords"], ["NextStep"])
        attempted_queries = [
            call.kwargs["args"]["keywords"][0] for call in search_source.call_args_list
        ]
        self.assertNotIn("FinalStep", attempted_queries)
        self.assertEqual(
            {source["function_name"] for source in report["evidence_sources"]},
            {"Scheduler::HandleRequest", "NextStep"},
        )

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key", "ROBOTOPS_LLM_ENABLED": "true"})
    @patch("agent_service.app.workflow.nodes.generate_structured_report")
    @patch("agent_service.app.workflow.nodes.generate_source_investigation")
    @patch("agent_service.app.workflow.nodes.search_source")
    def test_workflow_consumes_deepseek_source_plan_until_stop(
        self,
        search_source,
        generate_source_investigation,
        generate_structured_report,
    ):
        def source_result(*, args, **_kwargs):
            query = args["keywords"][0]
            if query == "ValidateRequest":
                return {
                    "ok": True,
                    "sources": [
                        {
                            "repo": "scheduler",
                            "file_path": "scheduler/src/validator.cpp",
                            "function_name": "ValidateRequest",
                            "matched_text": query,
                            "snippet": "bool ValidateRequest(Request request) { return request.valid(); }",
                        }
                    ],
                }
            return {
                "ok": True,
                "sources": [
                    {
                        "repo": "scheduler",
                        "file_path": "scheduler/src/handler.cpp",
                        "function_name": "Scheduler::HandleRequest",
                        "matched_text": "dispatch failed",
                        "snippet": "bool Scheduler::HandleRequest(Request request) { return ValidateRequest(request); }",
                    }
                ],
            }

        search_source.side_effect = source_result
        generate_source_investigation.side_effect = [
            {
                "queries": [
                    {
                        "module_name": "scheduler",
                        "query": "ValidateRequest",
                        "reason": "Verify the called validation branch.",
                        "evidence_ref": "scheduler/src/handler.cpp:Scheduler::HandleRequest",
                    }
                ],
                "stop": False,
            },
            {
                "queries": [],
                "stop": True,
                "stop_reason": "Validation implementation is now available.",
            },
        ]
        generate_structured_report.return_value = {
            "summary": "Validation source was inspected.",
            "suspected_module": "scheduler",
            "possible_causes": ["The validation branch rejects the request."],
            "evidence_logs": [],
            "evidence_sources": [],
            "recommended_actions": ["Check request validity fields."],
            "confidence": 0.8,
            "questions_for_human": [],
        }

        report = run_diagnosis_workflow(
            {
                "bug": {
                    "bug_id": "bug-deepseek-source-plan",
                    "title": "dispatch failed",
                    "description": "A scheduler request is rejected",
                    "robot_type": "ROBOT_TYPE_T",
                    "main_module": "scheduler",
                    "occurred_time": 1785396730000,
                },
                "logs": [
                    {
                        "module_name": "scheduler",
                        "file_name": "scheduler.log",
                        "line_no": 3,
                        "log_time": 1785396730010,
                        "log_level": "ERROR",
                        "message": "dispatch failed",
                    }
                ],
            }
        )

        self.assertEqual(search_source.call_count, 2)
        self.assertEqual(generate_source_investigation.call_count, 2)
        self.assertEqual(search_source.call_args_list[1].kwargs["args"]["keywords"], ["ValidateRequest"])
        self.assertEqual(report["generation_mode"], "deepseek")
        self.assertEqual(
            {source["function_name"] for source in report["evidence_sources"]},
            {"Scheduler::HandleRequest", "ValidateRequest"},
        )

    @patch("agent_service.app.workflow.nodes.search_source", side_effect=RuntimeError("local source unavailable"))
    def test_workflow_keeps_running_when_langchain_tool_raises(self, search_source):
        report = run_diagnosis_workflow(self.touch_payload)

        self.assertEqual(report["suspected_module"], "interaction")
        self.assertTrue(report["evidence_logs"])
        self.assertLessEqual(report["confidence"], 0.85)
        search_source.assert_called_once()

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
