import unittest
import json
import tempfile
from pathlib import Path

from agent_service.app.rag_retriever import LocalHybridRetriever, load_documents


class LocalHybridRetrieverTest(unittest.TestCase):
    def test_hybrid_retrieval_returns_rank_and_component_scores(self):
        retriever = LocalHybridRetriever(
            [
                {
                    "document_id": "touch-sop",
                    "main_module": "interaction",
                    "_search_text": "触摸事件 CheckTouch PASSIVE_DEFAULT self check",
                },
                {
                    "document_id": "move-sop",
                    "main_module": "mc",
                    "_search_text": "移动速度 odom SetVelocity timeout",
                },
            ]
        )

        result = retriever.search("触摸 CheckTouch", module="interaction", limit=2)

        self.assertEqual(result[0]["document_id"], "touch-sop")
        self.assertEqual(result[0]["retrieval"]["method"], "hybrid_bm25_tfidf")
        self.assertEqual(result[0]["retrieval"]["rank"], 1)
        self.assertGreater(result[0]["retrieval"]["bm25_score"], 0)
        self.assertGreater(result[0]["retrieval"]["vector_score"], 0)

    def test_document_cache_refreshes_when_source_file_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "knowledge.json"
            path.write_text(json.dumps({"items": [{"source_id": "one", "content": "touch"}]}), encoding="utf-8")
            self.assertEqual(load_documents((tmpdir,), collection="items")[0]["source_id"], "one")
            path.write_text(json.dumps({"items": [{"source_id": "two", "content": "move"}]}), encoding="utf-8")
            self.assertEqual(load_documents((tmpdir,), collection="items")[0]["source_id"], "two")


if __name__ == "__main__":
    unittest.main()
