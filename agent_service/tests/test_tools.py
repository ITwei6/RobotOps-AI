import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent_service.app.tools.log_tool import fetch_log_context
from agent_service.app.tools.source_tool import search_source


class LogToolTest(unittest.TestCase):
    @patch("agent_service.app.tools.log_tool.request.urlopen")
    def test_fetch_log_context_normalizes_brpc_json(self, urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps(
            {
                "response": {"code": 0, "message": "ok"},
                "logs": [
                    {
                        "module_name": "interaction",
                        "file_name": "interaction.log",
                        "line_no": 7,
                        "log_time": 1785396730150,
                        "log_level": "WARN",
                        "message": "ignore touch trigger",
                        "raw_line": "WARN ignore touch trigger",
                    }
                ],
            }
        ).encode("utf-8")
        urlopen.return_value.__enter__.return_value = response

        result = fetch_log_context(
            log_service_url="http://127.0.0.1:9501",
            timeout_seconds=1.0,
            args={
                "bug_id": "bug-1",
                "log_package_id": "pkg-1",
                "occurred_time": 1785396730000,
                "module_name": "interaction",
                "seconds_before": 60,
                "seconds_after": 60,
            },
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["logs"][0]["line_no"], 7)
        payload = urlopen.call_args.args[0].data.decode("utf-8")
        self.assertIn('"bug_id": ""', payload)
        self.assertIn('"package_id": "pkg-1"', payload)


class SourceToolTest(unittest.TestCase):
    def test_search_source_returns_match_with_snippet(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "interaction"
            source_dir = root / "src" / "scheduler" / "checker"
            source_dir.mkdir(parents=True)
            source_file = source_dir / "t1_checker.cpp"
            source_file.write_text(
                "\n".join(
                    [
                        "bool T1Checker::CheckTouch() {",
                        "  if (action == PASSIVE_DEFAULT) {",
                        '    LOG(WARNING) << "ignore touch trigger";',
                        "    return false;",
                        "  }",
                        "  return true;",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            result = search_source(
                roots=(tmpdir,),
                timeout_seconds=2.0,
                args={
                    "repo": "interaction",
                    "keywords": ["ignore touch trigger"],
                    "max_results": 5,
                },
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["sources"][0]["file_path"], "interaction/src/scheduler/checker/t1_checker.cpp")
        self.assertEqual(result["sources"][0]["function_name"], "T1Checker::CheckTouch")
        self.assertIn("bool T1Checker::CheckTouch()", result["sources"][0]["snippet"])
        self.assertIn("return false", result["sources"][0]["snippet"])
        self.assertIn("return true", result["sources"][0]["snippet"])

    def test_source_context_returns_generic_multiline_function_scope(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "navigation"
            root.mkdir()
            source_file = root / "dispatcher.cpp"
            source_file.write_text(
                "\n".join(
                    [
                        "void unrelated() {",
                        '  LOG(INFO) << "unrelated";',
                        "}",
                        "",
                        "Result NavigationManager::Dispatch(",
                        "    const Request& request) {",
                        "  auto route = BuildRoute(request);",
                        '  LOG(ERROR) << "dispatch route failed";',
                        "  if (!route.ok()) {",
                        "    return route.error();",
                        "  }",
                        "  return Send(route.value());",
                        "}",
                        "",
                        "void after() {",
                        '  LOG(INFO) << "after";',
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            result = search_source(
                roots=(),
                timeout_seconds=2.0,
                args={"repo": str(root), "keywords": ["dispatch route failed"]},
            )

        source = result["sources"][0]
        self.assertEqual(source["function_name"], "NavigationManager::Dispatch")
        self.assertIn("BuildRoute", source["snippet"])
        self.assertIn("return Send", source["snippet"])
        self.assertNotIn("unrelated", source["snippet"])
        self.assertNotIn('LOG(INFO) << "after"', source["snippet"])

    def test_source_context_returns_python_method_scope(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "agent"
            root.mkdir()
            source_file = root / "worker.py"
            source_file.write_text(
                "\n".join(
                    [
                        "class Worker:",
                        "    def execute(self, task):",
                        '        logger.error("worker execution failed")',
                        "        return self.retry(task)",
                        "",
                        "    @property",
                        "    def state(self):",
                        '        return "idle"',
                        "",
                        "def unrelated():",
                        "    return True",
                    ]
                ),
                encoding="utf-8",
            )

            result = search_source(
                roots=(),
                timeout_seconds=2.0,
                args={"repo": str(root), "keywords": ["worker execution failed"]},
            )

        source = result["sources"][0]
        self.assertEqual(source["function_name"], "Worker.execute")
        self.assertIn("return self.retry", source["snippet"])
        self.assertNotIn("@property", source["snippet"])
        self.assertNotIn("def unrelated", source["snippet"])

    def test_module_name_selects_matching_root_when_multiple_repositories_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            interaction_root = Path(tmpdir) / "interaction"
            mc_root = Path(tmpdir) / "mc"
            interaction_root.mkdir()
            mc_root.mkdir()
            (interaction_root / "handler.cpp").write_text(
                'void Handle() { LOG("shared failure"); }\n',
                encoding="utf-8",
            )
            (mc_root / "driver.cpp").write_text(
                'void Drive() { LOG("shared failure"); }\n',
                encoding="utf-8",
            )

            result = search_source(
                roots=(str(interaction_root), str(mc_root)),
                timeout_seconds=2.0,
                args={"module_name": "mc", "keywords": ["shared failure"]},
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["sources"][0]["repo"], "mc")
        self.assertEqual(result["sources"][0]["file_path"], "mc/driver.cpp")

    def test_local_repository_registry_metadata_is_attached_to_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "interaction"
            root.mkdir()
            (root / "checker.cpp").write_text(
                'bool T1Checker::CheckTouch() { return false; }\n', encoding="utf-8"
            )

            result = search_source(
                roots=(),
                timeout_seconds=2.0,
                args={"module_name": "interaction", "keywords": ["CheckTouch"]},
                repositories={
                    "interaction": {
                        "local_path": str(root),
                        "branch": "local-debug",
                        "commit": "pinned-local-revision",
                    }
                },
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["source_sync"]["action"], "use_local")
        self.assertEqual(result["sources"][0]["branch"], "local-debug")
        self.assertEqual(result["sources"][0]["commit"], "pinned-local-revision")

    def test_function_name_skips_uppercase_logging_macro(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "interaction"
            root.mkdir()
            source_file = root / "t1_checker.cpp"
            source_file.write_text(
                "\n".join(
                    [
                        "bool T1Checker::CheckTouch(int32_t type) {",
                        '  AIMRTE_WARN("ignore touch trigger");',
                        "  return false;",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            result = search_source(
                roots=(),
                timeout_seconds=2.0,
                args={"repo": str(root), "keywords": ["ignore touch trigger"]},
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["sources"][0]["function_name"], "T1Checker::CheckTouch")

    def test_nested_control_calls_resolve_to_owner_function_and_deduplicate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "control"
            root.mkdir()
            source_file = root / "validator.cpp"
            source_file.write_text(
                "\n".join(
                    [
                        "bool Controller::Validate() {",
                        "  if (StateStore::GetInstance()->CurrentState() == kBlocked) {",
                        '    LOG(ERROR) << "operation rejected";',
                        "    return false;",
                        "  }",
                        "  if (!config_.IsEnabled()) {",
                        '    LOG(ERROR) << "operation rejected";',
                        "    return false;",
                        "  }",
                        "  return true;",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            result = search_source(
                roots=(),
                timeout_seconds=2.0,
                args={"repo": str(root), "keywords": ["operation rejected"]},
            )

        self.assertTrue(result["ok"])
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["function_name"], "Controller::Validate")
        self.assertIn("config_.IsEnabled", result["sources"][0]["snippet"])


if __name__ == "__main__":
    unittest.main()
