import unittest

from ollama_caption_client import _normalize_ollama_endpoint, _tags_endpoint


class OllamaEndpointTests(unittest.TestCase):
    def test_scheme_less_base_url_is_supported(self):
        self.assertEqual(_normalize_ollama_endpoint("127.0.0.1:11434"), "http://127.0.0.1:11434/api/chat")
        self.assertEqual(_tags_endpoint("127.0.0.1:11434"), "http://127.0.0.1:11434/api/tags")

    def test_existing_api_paths_are_preserved(self):
        self.assertEqual(_normalize_ollama_endpoint("http://127.0.0.1:11434/api"), "http://127.0.0.1:11434/api/chat")
        self.assertEqual(_tags_endpoint("http://127.0.0.1:11434/api/chat"), "http://127.0.0.1:11434/api/tags")


if __name__ == "__main__":
    unittest.main()
