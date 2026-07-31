import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_service.app.main import list_source_repositories, update_source_repository
from agent_service.app.models import SourceRepositoryConfig
from agent_service.app.source_registry import load_repositories, save_repository


class SourceRegistryTest(unittest.TestCase):
    def test_repository_configuration_persists_by_module(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = str(Path(tmpdir) / "source-repositories.json")
            saved = save_repository(
                registry,
                "interaction",
                {"repo_url": "ssh://git.example/interaction.git", "branch": "main"},
            )
            loaded = load_repositories(registry)

        self.assertEqual(saved["branch"], "main")
        self.assertEqual(loaded["interaction"]["repo_url"], "ssh://git.example/interaction.git")

    def test_missing_registry_is_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(load_repositories(str(Path(tmpdir) / "missing.json")), {})

    def test_management_functions_update_module_repository(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = str(Path(tmpdir) / "source-repositories.json")
            with patch.dict("os.environ", {"ROBOTOPS_SOURCE_REPOSITORY_FILE": registry}):
                updated = update_source_repository(
                    "mc",
                    SourceRepositoryConfig(repo_url="ssh://git.example/mc.git", branch="release"),
                )
                listed = list_source_repositories()

        self.assertTrue(updated["ok"])
        self.assertEqual(listed["repositories"]["mc"]["branch"], "release")


if __name__ == "__main__":
    unittest.main()
