"""The extracted package: pure text helpers and defensive guards."""

import unittest
from email.message import Message

from hyperrouter_lib.guard import (
    INTERNAL_HEADER_PREFIXES,
    REFUSAL_NOTICE,
    detect_refusal,
    strip_internal_headers,
)
from hyperrouter_lib.text import (
    _cap,
    clip_display,
    content_to_text,
    display_width,
    estimate_tokens,
    human_count,
    messages_to_text,
    redact,
)


class TextModuleTest(unittest.TestCase):
    def test_tokens_and_redaction(self):
        self.assertEqual(estimate_tokens(""), 0)
        self.assertEqual(estimate_tokens("abcd"), 1)
        self.assertIn("sk-***", redact("token sk-abcdefghijkl"))
        self.assertIn("***", redact("Authorization: Bearer abc123"))

    def test_content_blocks_become_text(self):
        content = [{"type": "text", "text": "hello"},
                   {"type": "image_url", "image_url": {"url": "data:image/png;base64,xx"}}]
        self.assertEqual(content_to_text(content), "hello\n[image]")
        self.assertEqual(messages_to_text([{"role": "user", "content": "hi"}]),
                         "user: hi")

    def test_display_width_and_clipping_keep_wide_characters_whole(self):
        self.assertEqual(display_width("a界"), 3)
        self.assertEqual(clip_display("a界b", 2), "a")
        self.assertEqual(clip_display("a界b", 3), "a界")

    def test_cap_and_counts(self):
        self.assertIn("more characters", _cap("x" * 20, 10))
        self.assertEqual(human_count(999), "999")
        self.assertEqual(human_count(1500), "1.5k")


class GuardModuleTest(unittest.TestCase):
    def test_internal_headers_are_removed_case_insensitively(self):
        headers = {"X-Internal-Role": "admin", "x-admin-token": "secret",
                   "Content-Type": "application/json"}
        removed = strip_internal_headers(headers)
        self.assertCountEqual(removed, ["X-Internal-Role", "x-admin-token"])
        self.assertEqual(headers, {"Content-Type": "application/json"})
        self.assertIn("x-hyperrouter-internal-", INTERNAL_HEADER_PREFIXES)

    def test_message_headers_are_mutated_too(self):
        message = Message()
        message["X-Admin-Role"] = "root"
        message["Accept"] = "application/json"
        self.assertEqual(strip_internal_headers(message), ["X-Admin-Role"])
        self.assertEqual(message["Accept"], "application/json")

    def test_refusals_are_detected_but_deliveries_are_not(self):
        self.assertTrue(detect_refusal("I'm sorry, but I can't help with that."))
        self.assertTrue(detect_refusal("I cannot assist with this request."))
        self.assertFalse(detect_refusal("Here is the function:\n```python\ndef f():\n    pass\n```"))
        self.assertFalse(detect_refusal("Step 1: open the file. I'm unable to see your screen, "
                                       "so start there."))
        self.assertFalse(detect_refusal("Sure, here is how to do it."))

    def test_notice_does_not_promise_a_retry(self):
        self.assertIn("model declined", REFUSAL_NOTICE)
        self.assertIn("pick another model", REFUSAL_NOTICE)


if __name__ == "__main__":
    unittest.main()
