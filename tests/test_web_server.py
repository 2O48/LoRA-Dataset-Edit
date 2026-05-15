import unittest

from caption_workflow import (
    VALIDATION_EXISTING_CAPTION,
    apply_caption_result,
    build_modify_prompt,
    normalize_overwrite_mode,
    resolve_caption_request,
)


class WebServerCaptionModeTests(unittest.TestCase):
    def test_normalize_overwrite_mode_accepts_modify(self):
        self.assertEqual(normalize_overwrite_mode("modify"), "modify")
        self.assertEqual(normalize_overwrite_mode("unknown"), "overwrite")

    def test_apply_caption_result_append_preserves_existing(self):
        merged = apply_caption_result("soft light", "blue dress", "append")
        self.assertEqual(merged, "soft light, blue dress")

    def test_apply_caption_result_overwrite_returns_result(self):
        self.assertEqual(apply_caption_result("old text", "new text", "overwrite"), "new text")
        self.assertEqual(apply_caption_result("old text", "new text", "modify"), "new text")

    def test_build_modify_prompt_embeds_existing_and_instruction(self):
        prompt = build_modify_prompt("old caption", "make it shorter")
        self.assertIn("Existing caption:\nold caption", prompt)
        self.assertIn("Edit instruction:\nmake it shorter", prompt)
        self.assertIn("Return only the revised final caption.", prompt)

    def test_resolve_caption_request_uses_modify_when_existing_text_present(self):
        request = resolve_caption_request("old caption", "make it shorter", overwrite_mode="modify")
        self.assertEqual(request["write_mode"], "overwrite")
        self.assertTrue(request["used_modify"])
        self.assertFalse(request["fallback_to_overwrite"])
        self.assertIn("old caption", request["prompt"])

    def test_resolve_caption_request_falls_back_when_existing_text_missing(self):
        request = resolve_caption_request("", "describe image", overwrite_mode="modify")
        self.assertEqual(request["write_mode"], "overwrite")
        self.assertFalse(request["used_modify"])
        self.assertTrue(request["fallback_to_overwrite"])
        self.assertEqual(request["prompt"], "describe image")

    def test_validation_seed_is_non_empty_for_modify_validation(self):
        self.assertTrue(VALIDATION_EXISTING_CAPTION.strip())


if __name__ == "__main__":
    unittest.main()
