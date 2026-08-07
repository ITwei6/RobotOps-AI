import json
import tempfile
import unittest
from pathlib import Path

from agent_service.app.tools.knowledge_tool import search_knowledge


class KnowledgeToolTest(unittest.TestCase):
    def test_search_knowledge_returns_source_and_best_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "articles.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "source_id": "sop-interaction-001",
                                "main_module": "interaction",
                                "title": "触摸无响应排查 SOP",
                                "content": "先检查 self check 和 MC action，再确认 CheckTouch 是否拦截。",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps({"source_id": "other", "main_module": "mc", "content": "移动超时排查"}, ensure_ascii=False),
                    ]
                ),
                encoding="utf-8",
            )
            result = search_knowledge(
                (tmpdir,),
                {
                    "title": "触摸后没有反应",
                    "main_module": "interaction",
                    "keywords": ["CheckTouch"],
                },
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["knowledge_items"][0]["source"], "sop-interaction-001")
        self.assertIn("CheckTouch", result["knowledge_items"][0]["content"])
        self.assertEqual(result["retrieval"]["method"], "hybrid_bm25_tfidf")

    def test_missing_knowledge_root_is_empty(self):
        self.assertEqual(
            search_knowledge(("/path/that/does/not/exist",), {"title": "unknown"}),
            {"ok": True, "knowledge_items": []},
        )


if __name__ == "__main__":
    unittest.main()
