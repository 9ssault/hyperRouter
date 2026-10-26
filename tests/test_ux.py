"""TUI responsiveness helpers, retry/filter, routing errors and harness checks."""

import unittest
from types import SimpleNamespace

from tests.harness import hr


class FakeCurses:
    A_BOLD = 0
    A_DIM = 0
    A_REVERSE = 0
    BUTTON4_PRESSED = 1
    BUTTON5_PRESSED = 2
    BUTTON1_CLICKED = 4
    BUTTON1_PRESSED = 8
    KEY_MOUSE = 409
    error = Exception

    @staticmethod
    def color_pair(_pair):
        return 0


def fake_tui():
    app = hr.TuiApp.__new__(hr.TuiApp)
    app.c = FakeCurses()
    app.pairs = {}
    app.messages = []
    app.show_tokens = True
    app.filter = ""
    app.lines_cache = None
    app.ctx_tokens = 0
    app.ctx_cache = None
    app.busy = False
    app.stream_buf = ""
    app.spinner = 0
    return app


class TranscriptCacheTest(unittest.TestCase):
    def test_messages_are_rendered_once_per_change(self):
        app = fake_tui()
        app.messages = [{"role": "user", "content": "hello world"},
                        {"role": "assistant", "content": "hi", "meta": {"provider": "x"}}]
        first = app._message_lines(80)
        second = app._message_lines(80)
        self.assertIs(first, second)
        app.messages.append({"role": "info", "content": "done"})
        third = app._message_lines(80)
        self.assertIsNot(third, first)
        self.assertTrue(any("done" in text for text, _ in third))

    def test_filter_hides_non_matching_messages(self):
        app = fake_tui()
        app.messages = [{"role": "user", "content": "alpha"},
                        {"role": "assistant", "content": "beta"}]
        app.filter = "bet"
        lines = app._message_lines(80)
        text = "\n".join(line for line, _ in lines)
        self.assertIn("beta", text)
        self.assertNotIn("alpha", text)
        self.assertIn("filter: bet", text)

    def test_filter_clears_with_empty_value(self):
        app = fake_tui()
        app.messages = [{"role": "assistant", "content": "gamma"}]
        app.filter = "gamma"
        app._message_lines(80)
        app.filter = ""
        lines = app._message_lines(80)
        self.assertFalse(any("filter:" in line for line, _ in lines))


class MouseAndClickTest(unittest.TestCase):
    def test_wheel_scrolls_the_transcript(self):
        app = fake_tui()
        app.scroll = 0
        app.c = SimpleNamespace(BUTTON4_PRESSED=1, BUTTON5_PRESSED=2, error=Exception,
                                getmouse=lambda: (0, 0, 0, 0, 1))
        app._mouse()
        self.assertEqual(app.scroll, 3)
        app.c.getmouse = lambda: (0, 0, 0, 0, 2)
        app._mouse()
        self.assertEqual(app.scroll, 0)

    def test_click_on_a_command_hint_fills_the_input(self):
        app = fake_tui()
        app.buffer = ""
        app._click(("command", "/help"))
        self.assertEqual(app.buffer, "/help ")

    def test_click_on_a_file_hint_completes_the_at_path(self):
        app = fake_tui()
        app.buffer = "see @sr"
        app.file_matches = ["src/app.py"]
        app._click(("file", "src/app.py"))
        self.assertEqual(app.buffer, "see @src/app.py")
        self.assertEqual(app.file_matches, [])

    def test_click_on_a_model_row_chooses_it(self):
        app = fake_tui()
        app.model = "auto"
        app.overlay = {"kind": "model", "title": "Pick", "index": 0,
                       "items": [{"label": "a", "value": "auto-fast"},
                                 {"label": "b", "value": "auto-coding"}]}
        warnings = []
        app._warn = warnings.append
        app._click(("overlay", 1))
        self.assertEqual(app.model, "auto-coding")
        self.assertIsNone(app.overlay)
        self.assertTrue(warnings)


class RetryTest(unittest.TestCase):
    def test_retry_rewinds_to_the_last_user_message(self):
        app = fake_tui()
        app.messages = [{"role": "user", "content": "first"},
                        {"role": "assistant", "content": "answer"},
                        {"role": "user", "content": "second"},
                        {"role": "assistant", "content": "answer two"}]
        submitted = []
        app._persist = lambda: None
        app._warn = lambda text: None
        app._submit = lambda: submitted.append(app.buffer)
        app._retry()
        self.assertEqual([m["content"] for m in app.messages], ["first", "answer"])
        self.assertEqual(app.buffer, "second")
        self.assertEqual(submitted, ["second"])

    def test_retry_without_a_user_turn_warns(self):
        app = fake_tui()
        warnings = []
        app.busy = False
        app._warn = warnings.append
        app._retry()
        self.assertTrue(warnings)
        self.assertIn("nothing to retry", warnings[0])


class RoutingErrorTest(unittest.TestCase):
    def test_cooldown_and_rate_limit_are_explained(self):
        error = hr.routing_failure(
            [{"provider": "pollinations", "model": "openai", "status": 402,
              "error": "free limit reached"}],
            ["groq"])
        message = str(error)
        self.assertIn("pollinations/openai", message)
        self.assertIn("cooling down", message)
        self.assertIn("hyperrouter connect", message)

    def test_empty_errors_still_produce_a_message(self):
        message = str(hr.routing_failure([], []))
        self.assertIn("no candidate was tried", message)


class AgentHarnessTest(unittest.TestCase):
    def test_in_process_backend_is_always_available(self):
        self.assertTrue(hr.agent_available({"in_process": True, "command": []}))

    def test_missing_binary_is_unavailable_without_npx(self):
        self.assertFalse(hr.agent_available({"command": ["no-such-agent-binary-xyz"]}))

    def test_check_agent_reports_unknown_names(self):
        record = hr.check_agent("not-a-real-agent")
        self.assertFalse(record["ok"])
        self.assertIn("unknown agent", record["error"])
        self.assertGreaterEqual(record["latency_ms"], 0)

    def test_failure_message_offers_npx(self):
        backend = {"command": ["no-such-agent-binary-xyz", "run"], "npx": "pkg",
                   "headless": True}
        original = hr.shutil.which
        hr.AGENT_BACKENDS["missing-for-test"] = backend
        try:
            hr.shutil.which = (lambda name: None if name in {"no-such-agent-binary-xyz", "npx"}
                               else original(name))
            try:
                hr.run_agent("missing-for-test", "hi")
            except RuntimeError as exc:
                self.assertIn("npx -y pkg", str(exc))
            else:
                self.fail("run_agent should refuse a missing binary")
        finally:
            hr.shutil.which = original
            hr.AGENT_BACKENDS.pop("missing-for-test", None)


if __name__ == "__main__":
    unittest.main()
