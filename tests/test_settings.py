"""The extracted settings engine: defaults, coercion, validation and docs."""

import copy
import unittest

from hyperrouter_lib.settings import (
    DEFAULT_CONFIG,
    _MISSING,
    STRATEGIES,
    coerce_setting,
    deep_delete,
    deep_get,
    deep_set,
    flatten_config,
    format_setting,
    setting_entries,
    setting_kind,
    setting_value_text,
    validate_setting,
)


class DefaultsTest(unittest.TestCase):
    def test_defaults_cover_the_documented_sections(self):
        for key in ("chat.model", "agent.enabled", "routing.strategy", "ui.tui",
                    "server.port", "mcp.agent", "skills.auto_load"):
            self.assertIn(key, flatten_config(DEFAULT_CONFIG), key)
        self.assertEqual(DEFAULT_CONFIG["chat"]["model"], "auto")
        self.assertEqual(DEFAULT_CONFIG["routing"]["strategy"], "balanced")
        self.assertIn("balanced", STRATEGIES)

    def test_setting_entries_are_documented_and_marked_changed(self):
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["chat"]["stream"] = False
        entries = setting_entries(config)
        by_key = {entry["key"]: entry for entry in entries}
        self.assertTrue(by_key["chat.stream"]["changed"])
        self.assertFalse(by_key["chat.color"]["changed"])
        self.assertIn("Stream tokens", by_key["chat.stream"]["doc"])
        # Secrets and per-account data never become settings rows.
        self.assertNotIn("accounts", {entry["section"] for entry in entries})
        self.assertNotIn("providers", {entry["section"] for entry in entries})
        self.assertTrue(all(entry["doc"] for entry in entries))

    def test_entries_do_not_mutate_the_defaults(self):
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["chat"]["temperature"] = 1.4
        setting_entries(config)
        self.assertEqual(DEFAULT_CONFIG["chat"]["temperature"], 0.7)


class CoercionAndValidationTest(unittest.TestCase):
    def test_booleans_numbers_lists_and_objects(self):
        self.assertIs(coerce_setting("chat.stream", "off", True), False)
        self.assertEqual(coerce_setting("chat.history_limit", "25", 40), 25)
        self.assertEqual(coerce_setting("routing.temperature", "1.5", 0.7), 1.5)
        self.assertEqual(coerce_setting("chat.allow", "a, b", []), ["a", "b"])
        self.assertEqual(coerce_setting("chat.allow", '["x"]', []), ["x"])

    def test_validation_rejects_bad_values(self):
        with self.assertRaises(ValueError):
            validate_setting("server.port", 70000)
        with self.assertRaises(ValueError):
            validate_setting("routing.temperature", 3.0)
        with self.assertRaises(ValueError):
            validate_setting("routing.strategy", "fastest")
        with self.assertRaises(ValueError):
            validate_setting("agent.sandbox", "chroot")
        validate_setting("agent.sandbox", "bwrap")

    def test_kinds_drive_the_editor(self):
        self.assertEqual(setting_kind("chat.stream", True, True), "bool")
        self.assertEqual(setting_kind("chat.model", "auto", "auto"), "model")
        self.assertEqual(setting_kind("routing.strategy", "balanced", "balanced"), "enum")
        self.assertEqual(setting_kind("chat.history_limit", 40, 40), "number")
        self.assertEqual(setting_kind("routing.task_models", {}, _MISSING),
                         "json")


class DictionaryHelpersTest(unittest.TestCase):
    def test_deep_get_set_and_delete(self):
        node = copy.deepcopy(DEFAULT_CONFIG)
        self.assertEqual(deep_get(node, ["chat", "model"]), "auto")
        deep_set(node, ["chat", "model"], "auto-fast")
        self.assertEqual(node["chat"]["model"], "auto-fast")
        self.assertTrue(deep_delete(node, ["chat", "model"]))
        self.assertFalse(deep_delete(node, ["chat", "model"]))

    def test_formatting_and_display_values(self):
        self.assertEqual(format_setting(True), "true")
        self.assertEqual(format_setting(None), "null")
        self.assertEqual(format_setting(["a"]), '["a"]')
        self.assertEqual(setting_value_text({"kind": "bool", "value": True}), "on")
        self.assertEqual(setting_value_text({"kind": "text", "value": None}), "null")
        long = setting_value_text({"kind": "text", "value": "x" * 100}, 10)
        self.assertLessEqual(len(long), 10)
        self.assertTrue(long.endswith("…"))


if __name__ == "__main__":
    unittest.main()
