import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent_service.app.source_index import refresh_source_index
from agent_service.app.tools.source_tool import search_source


class SourceIndexTest(unittest.TestCase):
    def test_python_calls_and_topic_paths_are_searchable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = Path(tmpdir) / "agent"
            index_root = Path(tmpdir) / "index"
            repository.mkdir()
            (repository / "worker.py").write_text(
                "class Worker:\n"
                "    def execute(self, client):\n"
                "        client.publish('/robot/task/start')\n"
                "        return client.submit()\n",
                encoding="utf-8",
            )

            call_result = search_source(
                roots=(),
                timeout_seconds=2.0,
                index_root=str(index_root),
                args={"repo": str(repository), "keywords": ["submit"]},
            )
            topic_result = search_source(
                roots=(),
                timeout_seconds=2.0,
                index_root=str(index_root),
                args={"repo": str(repository), "keywords": ["/robot/task/start"]},
            )

        self.assertEqual(call_result["source_index"]["search_strategy"], "source_index")
        self.assertEqual(call_result["sources"][0]["function_name"], "Worker.execute")
        self.assertEqual(topic_result["source_index"]["search_strategy"], "source_index")
        self.assertEqual(topic_result["sources"][0]["function_name"], "Worker.execute")

    def test_remote_repository_update_is_pulled_and_incrementally_reindexed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            remote = root / "interaction.git"
            author = root / "author"
            workspace = root / "workspace"
            index_root = root / "index"
            self._git("init", "--bare", str(remote), cwd=root)
            self._git("init", "-b", "main", str(author), cwd=root)
            self._git("config", "user.email", "robotops@example.invalid", cwd=author)
            self._git("config", "user.name", "RobotOps Test", cwd=author)
            source = author / "scheduler.cpp"
            source.write_text("bool InitialCheck() { return true; }\n", encoding="utf-8")
            self._git("add", "scheduler.cpp", cwd=author)
            self._git("commit", "-m", "initial", cwd=author)
            self._git("remote", "add", "origin", str(remote), cwd=author)
            self._git("push", "-u", "origin", "main", cwd=author)
            repository_url = remote.as_uri()

            first = search_source(
                roots=(),
                timeout_seconds=5.0,
                workspace_root=str(workspace),
                index_root=str(index_root),
                args={"repo": repository_url, "branch": "main", "keywords": ["InitialCheck"]},
            )

            source.write_text("bool UpdatedCheck() { return true; }\n", encoding="utf-8")
            self._git("add", "scheduler.cpp", cwd=author)
            self._git("commit", "-m", "update checker", cwd=author)
            self._git("push", cwd=author)

            second = search_source(
                roots=(),
                timeout_seconds=5.0,
                workspace_root=str(workspace),
                index_root=str(index_root),
                args={"repo": repository_url, "branch": "main", "keywords": ["UpdatedCheck"]},
            )

        self.assertTrue(first["ok"])
        self.assertEqual(first["source_sync"]["action"], "clone")
        self.assertEqual(second["source_sync"]["action"], "pull")
        self.assertTrue(second["source_sync"]["updated"])
        self.assertNotEqual(
            second["source_sync"]["previous_revision"],
            second["source_sync"]["revision"],
        )
        self.assertEqual(second["source_index"]["action"], "updated")
        self.assertEqual(second["source_index"]["changed_files"], ["scheduler.cpp"])
        self.assertEqual(second["sources"][0]["function_name"], "UpdatedCheck")

    def test_search_uses_symbol_index_and_reuses_unchanged_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = Path(tmpdir) / "scheduler"
            index_root = Path(tmpdir) / "index"
            repository.mkdir()
            (repository / "handler.cpp").write_text(
                "bool Scheduler::HandleRequest(Request request) {\n"
                "  return ValidateRequest(request);\n"
                "}\n",
                encoding="utf-8",
            )
            (repository / "validator.cpp").write_text(
                "bool ValidateRequest(Request request) {\n"
                "  return request.valid();\n"
                "}\n",
                encoding="utf-8",
            )

            first = search_source(
                roots=(),
                timeout_seconds=2.0,
                index_root=str(index_root),
                args={"repo": str(repository), "keywords": ["ValidateRequest"]},
            )
            second = search_source(
                roots=(),
                timeout_seconds=2.0,
                index_root=str(index_root),
                args={"repo": str(repository), "keywords": ["ValidateRequest"]},
            )

        self.assertTrue(first["ok"])
        self.assertEqual(first["source_index"]["action"], "built")
        self.assertEqual(first["source_index"]["search_strategy"], "source_index")
        self.assertEqual(first["source_index"]["file_count"], 2)
        self.assertEqual(second["source_index"]["action"], "reused")
        self.assertEqual(
            {source["function_name"] for source in first["sources"]},
            {"Scheduler::HandleRequest", "ValidateRequest"},
        )

    def test_local_source_update_and_delete_refresh_the_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = Path(tmpdir) / "mc"
            index_root = Path(tmpdir) / "index"
            repository.mkdir()
            driver = repository / "driver.cpp"
            obsolete = repository / "obsolete.cpp"
            driver.write_text("bool StartMotor() { return LegacyCheck(); }\n", encoding="utf-8")
            obsolete.write_text("bool ObsoleteCheck() { return false; }\n", encoding="utf-8")

            initial = search_source(
                roots=(),
                timeout_seconds=2.0,
                index_root=str(index_root),
                args={"repo": str(repository), "keywords": ["LegacyCheck"]},
            )
            driver.write_text("bool StartMotor() { return SafetyCheck(); }\n", encoding="utf-8")
            obsolete.unlink()
            updated = search_source(
                roots=(),
                timeout_seconds=2.0,
                index_root=str(index_root),
                args={"repo": str(repository), "keywords": ["SafetyCheck"]},
            )

        self.assertEqual(initial["source_index"]["action"], "built")
        self.assertEqual(updated["source_index"]["action"], "updated")
        self.assertEqual(updated["source_index"]["changed_files"], ["driver.cpp"])
        self.assertEqual(updated["source_index"]["removed_files"], ["obsolete.cpp"])
        self.assertEqual(updated["sources"][0]["function_name"], "StartMotor")
        self.assertTrue(updated["sources"][0]["commit"].startswith("workspace-"))

    def test_revision_change_reindexes_only_git_changed_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = Path(tmpdir) / "interaction"
            index_root = Path(tmpdir) / "index"
            repository.mkdir()
            first_file = repository / "first.cpp"
            second_file = repository / "second.cpp"
            first_file.write_text("bool First() { return true; }\n", encoding="utf-8")
            second_file.write_text("bool Second() { return true; }\n", encoding="utf-8")
            file_indexer = MagicMock(
                side_effect=lambda path: {
                    "summary": path.name,
                    "symbols": [],
                    "calls": [],
                    "interfaces": [],
                }
            )

            refresh_source_index(
                repository_root=repository,
                index_root=str(index_root),
                revision="revision-a",
                file_indexer=file_indexer,
                timeout_seconds=2.0,
            )
            with patch(
                "agent_service.app.source_index._revision_changed_paths",
                return_value={"first.cpp"},
            ):
                _, status = refresh_source_index(
                    repository_root=repository,
                    index_root=str(index_root),
                    revision="revision-b",
                    file_indexer=file_indexer,
                    timeout_seconds=2.0,
                )

        self.assertEqual(file_indexer.call_count, 3)
        self.assertEqual(status["action"], "updated")
        self.assertEqual(status["previous_revision"], "revision-a")
        self.assertEqual(status["changed_files"], ["first.cpp"])

    @patch(
        "agent_service.app.tools.source_tool.refresh_source_index",
        side_effect=OSError("index directory unavailable"),
    )
    def test_index_failure_falls_back_to_full_text_search(self, _refresh_source_index):
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = Path(tmpdir) / "hal_camera"
            repository.mkdir()
            (repository / "camera.cpp").write_text(
                'bool OpenCamera() { LOG(ERROR) << "camera open failed"; return false; }\n',
                encoding="utf-8",
            )
            (repository / "troubleshooting.md").write_text(
                'Example: LOG(ERROR) << "camera open failed";\n',
                encoding="utf-8",
            )

            result = search_source(
                roots=(),
                timeout_seconds=2.0,
                index_root=str(Path(tmpdir) / "index"),
                args={"repo": str(repository), "keywords": ["camera open failed"]},
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["source_index"]["action"], "full_text_fallback")
        self.assertEqual(result["source_index"]["search_strategy"], "full_text")
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["function_name"], "OpenCamera")

    @staticmethod
    def _git(*args: str, cwd: Path) -> None:
        subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
