import unittest

from agent_service.evaluation import evaluate_cases


class EvaluationTest(unittest.TestCase):
    def test_evaluation_reports_agent_quality_metrics(self):
        cases = [
            {
                "case_id": "case-1",
                "request": {"bug": {"main_module": "scheduler"}},
                "expected": {
                    "suspected_module": "scheduler",
                    "required_source_functions": ["Scheduler::HandleRequest"],
                },
            }
        ]

        result = evaluate_cases(
            cases,
            runner=lambda _request: {
                "suspected_module": "scheduler",
                "evidence_sources": [
                    {
                        "file_path": "scheduler/handler.cpp",
                        "function_name": "Scheduler::HandleRequest",
                    }
                ],
                "diagnostic_trace": [
                    {"node": "normalize_input"},
                    {"node": "finalize"},
                ],
                "trace_id": "trace-1",
                "confidence": 0.8,
                "generation_mode": "deterministic_fallback",
            },
        )

        self.assertEqual(result["passed_cases"], 1)
        self.assertEqual(result["pass_rate"], 1.0)
        self.assertEqual(result["evidence_grounding_rate"], 1.0)
        self.assertEqual(result["trace_completion_rate"], 1.0)

    def test_evaluation_marks_missing_source_evidence_as_failed(self):
        result = evaluate_cases(
            [
                {
                    "case_id": "case-missing-source",
                    "request": {},
                    "expected": {
                        "suspected_module": "mc",
                        "required_source_functions": ["McController::SetMcAction"],
                    },
                }
            ],
            runner=lambda _request: {
                "suspected_module": "mc",
                "evidence_sources": [],
                "diagnostic_trace": [],
                "trace_id": "",
                "confidence": 0.2,
            },
        )

        self.assertEqual(result["passed_cases"], 0)
        self.assertEqual(result["required_source_hit_rate"], 0.0)
        self.assertEqual(result["trace_id_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
