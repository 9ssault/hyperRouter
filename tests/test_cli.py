import base64
import json
import os
import tempfile
import unittest
from pathlib import Path

from .harness import hr, require

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class WorkingDirectoryTest(unittest.TestCase):
    """Every test runs inside its own temp directory and restores cwd."""

    def setUp(self):
        self._cwd = Path.cwd()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        os.chdir(self.root)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()


class VersionAndParserTest(unittest.TestCase):
    def test_version_is_a_dotted_string(self):
        parts = hr.VERSION.split(".")
        self.assertEqual(len(parts), 3, hr.VERSION)
        self.assertTrue(all(part.isdigit() for part in parts), hr.VERSION)

    def test_parser_routes_agent_and_skills(self):
        parser = hr.build_parser()
        agent = parser.parse_args(["agent", "fix", "it", "--auto"])
        self.assertIs(agent.func, hr.cmd_agent)
        self.assertEqual(agent.task, ["fix", "it"])
        self.assertTrue(agent.auto)
        events = parser.parse_args(["agent", "go", "--json-events"])
        self.assertTrue(events.json_events)
        checked = parser.parse_args(["agents", "--test"])
        self.assertEqual(checked.test, "")
        named = parser.parse_args(["agents", "--test", "dsh"])
        self.assertEqual(named.test, "dsh")
        skills = parser.parse_args(["skills", "list"])
        self.assertIs(skills.func, hr.cmd_skills)
        self.assertEqual(skills.action, "list")

    def test_parser_exposes_expected_commands(self):
        parser = hr.build_parser()
        names = set(hr.main_commands(parser)) if hasattr(hr, "main_commands") else set(
            hr.build_parser()._subparsers._group_actions[0].choices)
        for expected in {"agent", "tui", "skills", "mcp", "doctor", "setup"}:
            self.assertIn(expected, names)

    def test_default_config_has_agent_and_routing_blocks(self):
        self.assertGreaterEqual(int(hr.DEFAULT_CONFIG["agent"]["max_rounds"]), 1)
        self.assertIn("routing", hr.DEFAULT_CONFIG)
        self.assertIn("mcp", hr.DEFAULT_CONFIG)


class SkillRegistryTest(WorkingDirectoryTest):
    def test_default_collections_are_declared(self):
        collections = require(self, "DEFAULT_SKILL_COLLECTIONS")
        self.assertIsInstance(collections, dict)
        self.assertGreaterEqual(len(collections), 15, collections)
        self.assertIn("anthropics/skills", collections)

    def test_default_installer_exists(self):
        ensure = require(self, "ensure_default_skills")
        self.assertTrue(callable(ensure))

    def test_project_pins_round_trip(self):
        path_fn = require(self, "project_skills_path")
        set_pins = require(self, "set_project_skills")
        get_pins = require(self, "project_skills")
        self.assertEqual(path_fn(), self.root / ".hyperrouter" / "skills.json")
        set_pins(["pdf", "mcp-builder"])
        self.assertEqual(get_pins(), ["pdf", "mcp-builder"])
        data = json.loads(path_fn().read_text(encoding="utf-8"))
        self.assertEqual(data["skills"], ["pdf", "mcp-builder"])


class VerificationDetectionTest(WorkingDirectoryTest):
    def test_pyproject_selects_pytest(self):
        detect = require(self, "detect_verify_command")
        (self.root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
        self.assertEqual(detect(self.root), "python3 -m pytest -q")

    def test_package_json_without_test_script_is_ignored(self):
        detect = require(self, "detect_verify_command")
        (self.root / "package.json").write_text(json.dumps({"scripts": {"build": "tsc"}}),
                                                encoding="utf-8")
        self.assertEqual(detect(self.root), "")
        (self.root / "package.json").write_text(json.dumps({"scripts": {"test": "vitest"}}),
                                                encoding="utf-8")
        self.assertEqual(detect(self.root), "npm test --silent")

    def test_makefile_test_target(self):
        detect = require(self, "detect_verify_command")
        (self.root / "Makefile").write_text("test:\n\tpytest -q\n", encoding="utf-8")
        self.assertEqual(detect(self.root), "make test")


class DisplayWidthTest(unittest.TestCase):
    def test_wide_characters_count_double(self):
        width = require(self, "display_width")
        self.assertEqual(width("abc"), 3)
        self.assertEqual(width("日本"), 4)

    def test_clip_never_splits_a_wide_character(self):
        clip = require(self, "clip_display")
        width = require(self, "display_width")
        clipped = clip("日本語", 3)
        self.assertLessEqual(width(clipped), 3)
        self.assertEqual(clipped, "日")

    def test_combining_marks_do_not_add_width(self):
        width = require(self, "display_width")
        self.assertEqual(width("e\u0301"), 1)


class ImageAttachmentTest(WorkingDirectoryTest):
    def test_png_is_accepted_as_a_data_url(self):
        load = require(self, "load_image_attachment")
        target = self.root / "pixel.png"
        target.write_bytes(PNG_1PX)
        image = load(str(target))
        self.assertEqual(image["name"], "pixel.png")
        self.assertTrue(image["url"].startswith("data:image/png;base64,"))

    def test_text_file_is_rejected(self):
        load = require(self, "load_image_attachment")
        target = self.root / "notes.txt"
        target.write_text("not an image", encoding="utf-8")
        with self.assertRaises(ValueError):
            load(str(target))

    def test_unknown_extension_is_rejected(self):
        load = require(self, "load_image_attachment")
        target = self.root / "pixel.bmp"
        target.write_bytes(PNG_1PX)
        with self.assertRaises(ValueError):
            load(str(target))


class UpdateLookupTest(unittest.TestCase):
    def test_repo_lookup_returns_a_path_or_none(self):
        lookup = require(self, "repo_dir_for_update")
        result = lookup()
        self.assertTrue(result is None or isinstance(result, Path))


if __name__ == "__main__":
    unittest.main()
