import unittest

from api_caption_client import _prompt_with_image_name_context as api_prompt_with_context
from caption_service import _prompt_with_image_name_context as local_prompt_with_context
from ollama_caption_client import _prompt_with_image_name_context as ollama_prompt_with_context


class CaptionFileNameContextTests(unittest.TestCase):
    def test_api_prompt_includes_dataset_and_file_names(self):
        prompt = api_prompt_with_context(
            "Caption this image.",
            image_name="subdir/sample",
            image_file_names=["sample.png"],
        )
        self.assertIn("Caption this image.", prompt)
        self.assertIn("Dataset item name: subdir/sample", prompt)
        self.assertIn("Image file name: sample.png", prompt)

    def test_ollama_prompt_includes_multiple_file_names(self):
        prompt = ollama_prompt_with_context(
            "Caption this image.",
            image_name="item",
            image_file_names=["control.png", "result.png"],
        )
        self.assertIn("Image file names: control.png, result.png", prompt)

    def test_local_prompt_is_unchanged_without_names(self):
        self.assertEqual(local_prompt_with_context("Caption this image."), "Caption this image.")


if __name__ == "__main__":
    unittest.main()
