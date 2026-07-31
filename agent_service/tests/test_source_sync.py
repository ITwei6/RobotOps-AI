import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_service.app.tools.source_tool import search_source, sync_source_repo


class SourceSyncTest(unittest.TestCase):
    def test_existing_git_repo_is_pulled_before_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "interaction"
            (repo / ".git").mkdir(parents=True)
            (repo / "checker.cpp").write_text(
                'bool T1Checker::CheckTouch() { return false; }\n', encoding="utf-8"
            )
            completed = subprocess.CompletedProcess([], 0, "abc123\n", "")
            with patch("agent_service.app.tools.source_tool._run_git", return_value=completed) as run_git:
                result = search_source(
                    roots=(tmpdir,),
                    timeout_seconds=2.0,
                    workspace_root=str(Path(tmpdir) / "cache"),
                    args={"repo": "interaction", "keywords": ["CheckTouch"]},
                )

        self.assertTrue(result["ok"])
        self.assertEqual(result["source_sync"]["action"], "pull")
        commands = [call.args[0] for call in run_git.call_args_list]
        self.assertIn(["git", "-C", str(repo), "pull", "--ff-only"], commands)

    def test_missing_remote_repo_returns_actionable_error(self):
        result = sync_source_repo(
            repo="https://example.invalid/interaction.git",
            workspace_root="/tmp/robotops-source-test",
            branch="main",
            commit="",
            timeout_seconds=0.1,
        )
        self.assertFalse(result["ok"])
        self.assertIn("git", result["error"].lower())


if __name__ == "__main__":
    unittest.main()
