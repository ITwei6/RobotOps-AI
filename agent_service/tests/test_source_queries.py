import unittest

from agent_service.app.source_queries import build_source_queries


class SourceQueryBuilderTest(unittest.TestCase):
    def test_builds_queries_from_runtime_log_without_rule_specific_hints(self):
        queries = build_source_queries(
            bug={
                "title": "Command dispatch times out",
                "description": "The command is not acknowledged",
                "occurred_time": 1700000000000,
            },
            logs=[
                {
                    "module_name": "control",
                    "log_level": "ERROR",
                    "log_time": 1700000000020,
                    "message": "Request SendCommand failed, request_id: 81234, timeout_ms: 3000",
                }
            ],
            module_name="control",
        )

        self.assertIn("Request SendCommand failed", queries)
        self.assertIn("SendCommand", queries)
        self.assertLess(
            queries.index("Request SendCommand failed"),
            queries.index("SendCommand"),
        )
        self.assertNotIn("request_id: 81234", queries)
        self.assertFalse(any("81234" in query for query in queries))

    def test_uses_only_logs_owned_by_requested_module(self):
        queries = build_source_queries(
            bug={"title": "", "description": "", "occurred_time": 0},
            logs=[
                {
                    "module_name": "navigation",
                    "log_level": "WARN",
                    "message": "NavigationManager::DispatchTask returned invalid state",
                },
                {
                    "module_name": "vision",
                    "log_level": "ERROR",
                    "message": "FrameDecoder::Decode failed permanently",
                },
            ],
            module_name="navigation",
        )

        self.assertIn("NavigationManager::DispatchTask", queries)
        self.assertFalse(any("FrameDecoder" in query for query in queries))

    def test_uses_bug_text_as_fallback_when_module_has_no_logs(self):
        queries = build_source_queries(
            bug={
                "title": "MapLoader initialization failed",
                "description": "load_offline_map returns an empty result",
                "occurred_time": 0,
            },
            logs=[],
            module_name="mapping",
        )

        self.assertTrue(any("MapLoader" in query for query in queries))
        self.assertTrue(any("load_offline_map" in query for query in queries))


if __name__ == "__main__":
    unittest.main()
