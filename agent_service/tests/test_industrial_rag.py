import json
import unittest
from unittest.mock import MagicMock, patch

from agent_service.app.industrial_rag import EmbeddingClient, _chunks


class IndustrialRagTest(unittest.TestCase):
    def test_chunks_preserve_document_and_content_metadata(self):
        chunks = list(_chunks({
            "case_id": "case-1",
            "title": "Touch failure",
            "description": "The touch event was ignored.",
            "causes": ["CheckTouch rejected the action"],
            "source": "case-1",
        }, "cases"))

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["document_id"], "case-1")
        self.assertEqual(chunks[0]["source_type"], "history_case")
        self.assertIn("Touch failure", chunks[0]["content"])
        self.assertIn("CheckTouch", chunks[0]["content"])

    @patch("agent_service.app.industrial_rag.request.urlopen")
    def test_embedding_client_reads_openai_compatible_response(self, urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps({"data": [{"index": 0, "embedding": [0.1, 0.2]}]}).encode()
        urlopen.return_value.__enter__.return_value = response
        client = EmbeddingClient(
            url="http://embedding.test/v1",
            api_key="test-key",
            model="test-embedding",
            timeout=1.0,
            dimensions=2,
        )

        self.assertEqual(client.embed(["touch failure"]), [[0.1, 0.2]])
        request_value = urlopen.call_args.args[0]
        self.assertEqual(request_value.full_url, "http://embedding.test/v1/embeddings")
        self.assertEqual(request_value.get_header("Authorization"), "Bearer test-key")


if __name__ == "__main__":
    unittest.main()
