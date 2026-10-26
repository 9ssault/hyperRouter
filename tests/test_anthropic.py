"""Anthropic Messages <-> OpenAI chat translation used by the Claude shim."""

import unittest

from tests.harness import hr


class AnthropicRequestTest(unittest.TestCase):
    def test_system_and_text_blocks_become_messages(self):
        messages, tools = hr.anthropic_to_openai({
            "system": [{"type": "text", "text": "be terse"}],
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "hello"},
                {"type": "text", "text": "world"}]}],
        })
        self.assertEqual(messages[0], {"role": "system", "content": "be terse"})
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("hello", messages[1]["content"])
        self.assertIn("world", messages[1]["content"])
        self.assertEqual(tools, [])

    def test_tool_use_and_tool_result_round_trip(self):
        messages, tools = hr.anthropic_to_openai({
            "messages": [
                {"role": "user", "content": "weather?"},
                {"role": "assistant", "content": [
                    {"type": "text", "text": "checking"},
                    {"type": "tool_use", "id": "toolu_1", "name": "get_weather",
                     "input": {"city": "Paris"}}]},
                {"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": "toolu_1",
                     "content": [{"type": "text", "text": "18C"}]}]},
            ],
            "tools": [{"name": "get_weather", "description": "weather",
                       "input_schema": {"type": "object", "properties": {}}}],
        })
        assistant = [m for m in messages if m["role"] == "assistant"][0]
        self.assertEqual(assistant["tool_calls"][0]["function"]["name"], "get_weather")
        self.assertIn("Paris", assistant["tool_calls"][0]["function"]["arguments"])
        tool_message = [m for m in messages if m["role"] == "tool"][0]
        self.assertEqual(tool_message["tool_call_id"], "toolu_1")
        self.assertEqual(tool_message["content"], "18C")
        self.assertEqual(tools[0]["function"]["name"], "get_weather")

    def test_base64_image_becomes_image_url(self):
        messages, _ = hr.anthropic_to_openai({
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": "what is this"},
                {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                             "data": "AAAA"}}]}],
        })
        parts = messages[0]["content"]
        self.assertEqual(parts[1]["type"], "image_url")
        self.assertTrue(parts[1]["image_url"]["url"].startswith("data:image/png;base64,"))


class AnthropicResponseTest(unittest.TestCase):
    def test_text_response_has_end_turn(self):
        payload = hr.openai_response_to_anthropic(
            {"choices": [{"message": {"content": "hi"}}],
             "usage": {"prompt_tokens": 4, "completion_tokens": 2}}, "auto")
        self.assertEqual(payload["content"], [{"type": "text", "text": "hi"}])
        self.assertEqual(payload["stop_reason"], "end_turn")
        self.assertEqual(payload["usage"], {"input_tokens": 4, "output_tokens": 2})

    def test_tool_call_becomes_tool_use_block(self):
        payload = hr.openai_response_to_anthropic(
            {"choices": [{"message": {"content": "", "tool_calls": [
                {"id": "call_9", "function": {"name": "read_file",
                                              "arguments": '{"path": "a.txt"}'}}]}}]},
            "auto")
        block = payload["content"][0]
        self.assertEqual(block["type"], "tool_use")
        self.assertEqual(block["id"], "call_9")
        self.assertEqual(block["input"], {"path": "a.txt"})
        self.assertEqual(payload["stop_reason"], "tool_use")

    def test_empty_response_is_replaced_by_the_caller(self):
        payload = hr.openai_response_to_anthropic({"choices": [{"message": {}}]}, "auto")
        self.assertEqual(payload["content"], [])
        self.assertEqual(payload["stop_reason"], "end_turn")


if __name__ == "__main__":
    unittest.main()
