import unittest
from unittest.mock import patch

from agent_service.app.llm.source_planner import (
    SourceInvestigationPlan,
    build_deterministic_source_investigation,
    generate_source_investigation,
    ground_source_investigation,
)


class FakeSourcePlannerDeepSeek:
    last_method = ""
    last_prompt = ""

    def __init__(self, model, temperature, max_retries):
        self.model = model

    def with_structured_output(self, schema, *, method):
        self.schema = schema
        FakeSourcePlannerDeepSeek.last_method = method
        return self

    def invoke(self, prompt):
        FakeSourcePlannerDeepSeek.last_prompt = prompt
        return SourceInvestigationPlan(
            findings=["HandleRequest delegates validation."],
            unresolved_questions=["Does validation reject this request?"],
            queries=[
                {
                    "module_name": "scheduler",
                    "query": "ValidateRequest",
                    "reason": "Follow the called validator.",
                    "evidence_ref": "scheduler/src/handler.cpp:Scheduler::HandleRequest",
                }
            ],
        )


class SourcePlannerTest(unittest.TestCase):
    def setUp(self):
        self.source = {
            "repo": "scheduler",
            "file_path": "scheduler/src/handler.cpp",
            "function_name": "Scheduler::HandleRequest",
            "matched_text": "dispatch request failed",
            "snippet": "\n".join(
                [
                    "1: bool Scheduler::HandleRequest(const Request& request) {",
                    "2:   auto task = TaskFactory::GetInstance()->CreateTask(request);",
                    "3:   if (!ValidateRequest(request)) { return false; }",
                    "4:   worker_->Submit(task);",
                    '5:   AIMRTE_ERROR("dispatch request failed");',
                    "6:   return true;",
                    "7: }",
                ]
            ),
        }

    def test_generate_source_investigation_uses_json_mode_and_schema(self):
        with patch(
            "agent_service.app.llm.source_planner.ChatDeepSeek",
            FakeSourcePlannerDeepSeek,
        ):
            plan = generate_source_investigation(
                model="deepseek-v4-flash",
                bug={"title": "dispatch failed", "main_module": "scheduler"},
                logs=[{"module_name": "scheduler", "message": "dispatch request failed"}],
                sources=[self.source],
                allowed_modules=["scheduler"],
                attempted_queries=[("scheduler", "dispatch request failed")],
            )

        self.assertEqual(plan["queries"][0]["query"], "ValidateRequest")
        self.assertEqual(FakeSourcePlannerDeepSeek.last_method, "json_mode")
        self.assertIn("SourceInvestigationPlan JSON schema", FakeSourcePlannerDeepSeek.last_prompt)
        self.assertIn("scheduler/src/handler.cpp:Scheduler::HandleRequest", FakeSourcePlannerDeepSeek.last_prompt)

    def test_grounding_rejects_unobserved_queries_modules_and_duplicates(self):
        plan = ground_source_investigation(
            {
                "queries": [
                    {
                        "module_name": "scheduler",
                        "query": "ValidateRequest",
                        "evidence_ref": "scheduler/src/handler.cpp:Scheduler::HandleRequest",
                    },
                    {
                        "module_name": "scheduler",
                        "query": "InventedFunction",
                        "evidence_ref": "scheduler/src/handler.cpp:Scheduler::HandleRequest",
                    },
                    {
                        "module_name": "unknown_module",
                        "query": "CreateTask",
                        "evidence_ref": "scheduler/src/handler.cpp:Scheduler::HandleRequest",
                    },
                    {
                        "module_name": "scheduler",
                        "query": "Submit",
                        "evidence_ref": "scheduler/src/handler.cpp:Scheduler::HandleRequest",
                    },
                ]
            },
            sources=[self.source],
            allowed_modules=["scheduler"],
            attempted_queries=[("scheduler", "Submit")],
        )

        self.assertEqual([item["query"] for item in plan["queries"]], ["ValidateRequest"])
        self.assertEqual(plan["rejected_query_count"], 3)
        self.assertEqual(
            plan["queries"][0]["evidence_ref"],
            "scheduler/src/handler.cpp:Scheduler::HandleRequest",
        )

    def test_deterministic_plan_extracts_calls_without_owner_or_logging_symbols(self):
        plan = build_deterministic_source_investigation(
            sources=[self.source],
            module_name="scheduler",
            allowed_modules=["scheduler"],
            attempted_queries=[("scheduler", "ValidateRequest")],
        )

        queries = [item["query"] for item in plan["queries"]]
        self.assertIn("CreateTask", queries)
        self.assertIn("Submit", queries)
        self.assertNotIn("Scheduler::HandleRequest", queries)
        self.assertNotIn("TaskFactory::GetInstance", queries)
        self.assertFalse(any("LOG" in query for query in queries))
        self.assertFalse(any(query.endswith(("_WARN", "_ERROR")) for query in queries))


if __name__ == "__main__":
    unittest.main()
