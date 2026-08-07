import unittest
from unittest.mock import patch

from embedding_service import app as embedding_app


class _FakeModel:
    def embed(self, texts):
        for text in texts:
            yield [len(text), 3.0, 4.0]


class EmbeddingServiceTest(unittest.TestCase):
    def setUp(self):
        embedding_app._model = None

    def test_openai_compatible_response_is_normalized(self):
        with patch.object(embedding_app, "TextEmbedding", return_value=_FakeModel()):
            result = embedding_app.embeddings(
                embedding_app.EmbeddingRequest(input=["触摸无响应", "mc action"])
            )
        self.assertEqual(result["object"], "list")
        self.assertEqual(len(result["data"]), 2)
        self.assertAlmostEqual(sum(value * value for value in result["data"][0]["embedding"]), 1.0)
        self.assertEqual([item["index"] for item in result["data"]], [0, 1])

    def test_model_is_loaded_lazily(self):
        self.assertFalse(embedding_app.health()["ready"])
        with patch.object(embedding_app, "TextEmbedding", return_value=_FakeModel()):
            embedding_app.embeddings(embedding_app.EmbeddingRequest(input="日志上下文"))
        self.assertTrue(embedding_app.health()["ready"])


if __name__ == "__main__":
    unittest.main()
