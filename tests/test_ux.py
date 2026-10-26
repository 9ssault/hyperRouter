"""TUI responsiveness helpers, retry/filter, routing errors and harness checks."""

import unittest
from datetime import datetime, timedelta, timezone
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
    KEY_UP = -1
    KEY_DOWN = -2
    KEY_PPAGE = -3
    KEY_NPAGE = -4
    KEY_HOME = -5
    KEY_END = -6
    KEY_LEFT = -7
    KEY_RIGHT = -8
    KEY_BACKSPACE = -9
    KEY_ENTER = "\r"
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
    app.config = hr.load_config()
    app.settings_cache = None
    app.settings_sections = []
    app._model_items_cache = None
    app.click_targets = []
    app.model = "auto"
    app.notice = ""
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


class SettingsBrowserTest(unittest.TestCase):
    def setUp(self):
        self.app = fake_tui()
        self.toasts = []
        self.app._warn = self.toasts.append

    def test_settings_are_grouped_and_explained(self):
        self.app._open_settings()
        self.assertIn("chat", self.app.settings_sections)
        self.assertIn("agent", self.app.settings_sections)
        entries = self.app.overlay["items"]
        self.assertTrue(entries)
        self.assertTrue(all(entry.get("doc") for entry in entries))
        self.assertTrue(all(entry.get("section") == "chat" for entry in entries))
        self.assertNotIn("accounts", {entry["key"] for entry in entries})

    def test_typing_filters_across_sections_and_esc_returns(self):
        self.app._open_settings()
        for character in "sandbox":
            self.app._settings_key(character)
        hits = [entry["key"] for entry in self.app.overlay["items"]]
        self.assertIn("agent.sandbox", hits)
        self.assertNotIn("chat.stream", hits)
        self.app._settings_key("\x15")
        self.assertEqual(self.app.overlay["query"], "")
        self.app._settings_key("\x1b")
        self.assertIsNone(self.app.overlay)

    def test_enter_toggles_a_boolean_and_saves_it(self):
        self.app._open_settings()
        items = self.app.overlay["items"]
        index = next(i for i, entry in enumerate(items) if entry["key"] == "chat.stream")
        self.app.overlay["index"] = index
        before = bool(hr.load_config()["chat"]["stream"])
        self.app._settings_key("\r")
        self.assertEqual(hr.load_config()["chat"]["stream"], not before)
        self.assertTrue(any("chat.stream" in toast for toast in self.toasts))
        # Put the test config back so later tests see the defaults.
        self.app._settings_apply(items[index], before)

    def test_number_editor_writes_a_valid_value_and_keeps_editing_on_error(self):
        self.app._open_settings()
        items = self.app.overlay["items"]
        index = next(i for i, entry in enumerate(items) if entry["key"] == "chat.history_limit")
        self.app._settings_choose(index)
        self.assertEqual(self.app.overlay["mode"], "edit")
        self.app._settings_key("\x15")
        for character in "1":
            self.app._settings_key(character)
        self.app._settings_key("\r")
        self.assertEqual(self.app.overlay["mode"], "edit")  # 1 is below the minimum
        self.app._settings_key("\x15")
        for character in "25":
            self.app._settings_key(character)
        self.app._settings_key("\r")
        self.assertEqual(hr.load_config()["chat"]["history_limit"], 25)
        self.assertEqual(self.app.overlay["mode"], "list")
        self.app._settings_apply(self.app._settings_selected(), 40)

    def test_model_setting_opens_the_picker_and_saves_the_choice(self):
        self.app._open_settings()
        self.app.overlay["query"] = "chat.model"
        self.app._settings_refilter()
        self.app._settings_choose(0)
        self.assertEqual(self.app.overlay["kind"], "model")
        self.assertEqual(self.app.overlay.get("for_setting"), "chat.model")
        index = next(i for i, item in enumerate(self.app.overlay["items"])
                     if item["value"] == "auto-coding")
        self.app._overlay_choose(index)
        self.assertEqual(hr.load_config()["chat"]["model"], "auto-coding")
        entry = next(entry for entry in hr.setting_entries(hr.load_config())
                     if entry["key"] == "chat.model")
        self.app._settings_apply(entry, "auto")

    def test_picking_a_model_from_the_picker_persists_it(self):
        self.app._open_model_picker()
        index = next(i for i, item in enumerate(self.app.overlay["items"])
                     if item["value"] == "auto-fast")
        self.app._overlay_choose(index)
        self.assertEqual(hr.load_config()["chat"]["model"], "auto-fast")
        self.app._save_default_model("auto")

    def test_changed_settings_are_marked_and_reset_with_ctrl_r(self):
        self.app._open_settings()
        items = self.app.overlay["items"]
        index = next(i for i, entry in enumerate(items) if entry["key"] == "chat.color")
        self.app.overlay["index"] = index
        before = bool(hr.load_config()["chat"]["color"])
        self.app._settings_key("\r")
        self.assertTrue(items[index]["changed"])
        self.app._settings_key("\x12")
        self.assertEqual(hr.load_config()["chat"]["color"], before)
        self.assertFalse(items[index]["changed"])

    def test_model_picker_lists_every_routable_model_not_only_live_ones(self):
        catalog = {"models": [
            {"id": "alpha/one", "provider": "alpha", "model": "one", "routable": True,
             "free_type": "recurring-daily", "context": 32000},
            {"id": "beta/two", "provider": "beta", "model": "two", "routable": True,
             "free_type": "keyless", "context": 16000},
        ]}
        original = (hr.load_catalog, hr.discover_accounts)
        hr.load_catalog = lambda force=False: catalog
        hr.discover_accounts = lambda config=None: []
        try:
            items = self.app._model_picker_items()
        finally:
            hr.load_catalog, hr.discover_accounts = original
        values = {item["value"] for item in items}
        self.assertIn("alpha/one", values)
        self.assertIn("beta/two", values)
        self.assertIn("auto", values)
        self.assertGreater(len(items), 2)
        self.assertIn("no account added", next(item["label"] for item in items
                                               if item["value"] == "alpha/one"))


class CoolingFallbackTest(unittest.TestCase):
    def test_a_cooling_account_still_produces_a_candidate(self):
        account = {"id": "acct-cooling", "provider": "alpha", "label": "test",
                   "disabled": False, "quota": {}}
        catalog = {"models": [{"id": "alpha/one", "provider": "alpha", "model": "one",
                               "routable": True, "free_type": "recurring-daily",
                               "context": 32000, "tos": "ok", "tools": True}]}
        conn = hr.connect()
        conn.execute("DELETE FROM health")
        conn.execute("INSERT INTO health(account_id, cooldown_until) VALUES (?, ?)",
                     (account["id"], (datetime.now(timezone.utc)
                                      + timedelta(seconds=120)).isoformat()))
        conn.commit()
        conn.close()
        original = (hr.load_catalog, hr.discover_accounts)
        hr.load_catalog = lambda force=False: catalog
        hr.discover_accounts = lambda config=None: [account]
        try:
            candidates = hr.pick_models("chat", limit=3)
        finally:
            hr.load_catalog, hr.discover_accounts = original
            conn = hr.connect()
            conn.execute("DELETE FROM health")
            conn.commit()
            conn.close()
        self.assertTrue(candidates)
        self.assertEqual(candidates[0]["model"]["id"], "alpha/one")

    def test_empty_route_message_counts_the_catalog(self):
        original = hr.load_catalog
        hr.load_catalog = lambda force=False: {"models": [
            {"id": "x/y", "routable": True, "free_type": "free"},
            {"id": "x/z", "routable": True, "free_type": "discontinued"},
        ]}
        try:
            message = hr.no_free_model_message()
        finally:
            hr.load_catalog = original
        self.assertIn("1 free models are in the catalog", message)
        self.assertIn("hyperrouter connect", message)


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
