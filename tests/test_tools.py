import os
import tempfile
import unittest
from pathlib import Path

from .harness import hr, require


class ToolTest(unittest.TestCase):
    def setUp(self):
        self._cwd = Path.cwd()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        os.chdir(self.root)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()


class DiffPreviewTest(ToolTest):
    def test_unified_diff_marks_removed_and_added_lines(self):
        path = self.root / "demo.txt"
        preview = hr.diff_preview(path, "alpha beta\nsecond\n", "alpha BETA\nsecond\n")
        self.assertIn("-alpha beta", preview)
        self.assertIn("+alpha BETA", preview)
        self.assertIn("@@", preview)
        self.assertIn("demo.txt", preview)

    def test_identical_content_says_no_change(self):
        path = self.root / "same.txt"
        self.assertIn("no change", hr.diff_preview(path, "x\n", "x\n"))

    def test_new_file_preview_is_all_additions(self):
        preview = hr.diff_preview(self.root / "new.txt", "", "one\ntwo\n")
        self.assertIn("+one", preview)
        self.assertIn("+two", preview)


class ApprovalTest(ToolTest):
    def test_denied_edit_leaves_the_file_untouched(self):
        target = self.root / "edit.txt"
        target.write_text("alpha beta\n", encoding="utf-8")
        seen = []

        def deny(kind, detail, preview=""):
            seen.append((kind, detail, preview))
            return False

        out = hr.execute_tool("edit_file",
                              {"path": "edit.txt", "old_string": "beta", "new_string": "BETA"},
                              deny, ctx={"root": str(self.root)})
        self.assertIn("denied", out)
        self.assertEqual(target.read_text(encoding="utf-8"), "alpha beta\n")
        self.assertEqual(seen[0][0], "edit")
        if len(seen[0]) > 2:  # builds before the diff viewer only pass two arguments
            self.assertIn("+alpha BETA", seen[0][2])

    def test_approved_edit_applies_and_tracks_the_change(self):
        target = self.root / "edit.txt"
        target.write_text("alpha beta\n", encoding="utf-8")
        ctx = {}
        out = hr.execute_tool("edit_file",
                              {"path": "edit.txt", "old_string": "beta", "new_string": "BETA"},
                              lambda kind, detail, preview="": True, ctx=ctx)
        self.assertIn("edited", out)
        self.assertEqual(target.read_text(encoding="utf-8"), "alpha BETA\n")
        if ctx.get("changed"):
            self.assertIn("edit.txt", ctx["changed"])

    def test_denied_write_creates_nothing(self):
        out = hr.execute_tool("write_file", {"path": "new.txt", "content": "hello\n"},
                              lambda kind, detail, preview="": False,
                              ctx={"root": str(self.root)})
        self.assertIn("denied", out)
        self.assertFalse((self.root / "new.txt").exists())

    def test_approved_write_creates_the_file(self):
        out = hr.execute_tool("write_file", {"path": "new.txt", "content": "hello\n"},
                              lambda kind, detail, preview="": True,
                              ctx={"root": str(self.root)})
        self.assertIn("wrote", out)
        self.assertEqual((self.root / "new.txt").read_text(encoding="utf-8"), "hello\n")

    def test_denied_command_does_not_run(self):
        marker = self.root / "should-not-exist.txt"
        out = hr.execute_tool("run_command",
                              {"command": f"touch {marker.name}"},
                              lambda kind, detail, preview="": False,
                              ctx={"root": str(self.root)})
        self.assertIn("denied", out)
        self.assertFalse(marker.exists())


class LocalToolTest(ToolTest):
    def test_read_file_returns_numbered_lines(self):
        (self.root / "sample.txt").write_text("first\nsecond\n", encoding="utf-8")
        out = hr.execute_tool("read_file", {"path": "sample.txt"}, ctx={"root": str(self.root)})
        self.assertIn("1  first", out)
        self.assertIn("2  second", out)

    def test_list_dir_lists_entries(self):
        (self.root / "alpha.py").write_text("x = 1\n", encoding="utf-8")
        out = hr.execute_tool("list_dir", {"path": "."}, ctx={"root": str(self.root)})
        self.assertIn("alpha.py", out)

    def test_search_finds_content(self):
        (self.root / "needle.txt").write_text("a needle in here\n", encoding="utf-8")
        out = hr.execute_tool("search", {"pattern": "needle", "path": "."},
                              ctx={"root": str(self.root)})
        self.assertIn("needle", out)

    def test_paths_outside_the_workspace_are_refused(self):
        outside = Path(self._tmp.name).parent / "outside-secret.txt"
        out = hr.execute_tool("read_file", {"path": str(outside)},
                              ctx={"root": str(self.root)})
        self.assertIn("error", out.lower())
        self.assertIn("outside", out.lower())


class WebSafetyTest(ToolTest):
    def test_loopback_is_refused(self):
        require(self, "_assert_public_url")
        out = hr.execute_tool("web_fetch", {"url": "http://127.0.0.1:8787/v1/models"})
        self.assertIn("error", out.lower())
        self.assertIn("refus", out.lower())

    def test_link_local_metadata_address_is_refused(self):
        require(self, "_assert_public_url")
        out = hr.execute_tool("web_fetch", {"url": "http://169.254.169.254/latest/meta-data/"})
        self.assertIn("error", out.lower())
        self.assertIn("refus", out.lower())

    def test_non_http_scheme_is_refused(self):
        require(self, "_assert_public_url")
        out = hr.execute_tool("web_fetch", {"url": "file:///etc/passwd"})
        self.assertIn("error", out.lower())


class SubagentDispatchTest(ToolTest):
    def test_overlapping_files_are_refused_before_any_model_call(self):
        subagent = require(self, "tool_subagent")
        real_route = hr.route_once
        hr.route_once = lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("no model call should happen"))
        try:
            out = subagent({"tasks": [
                {"files": ["a.txt"], "task": "edit a"},
                {"files": ["a.txt"], "task": "edit a again"},
            ]}, approve=lambda *a: True)
        finally:
            hr.route_once = real_route
        self.assertIn("assigned to more than one worker", out)

    def test_empty_task_list_is_refused(self):
        subagent = require(self, "tool_subagent")
        self.assertIn("error", subagent({"tasks": []}))

    def test_nested_workers_are_refused(self):
        subagent = require(self, "tool_subagent")
        out = subagent({"tasks": [{"task": "x"}]}, ctx={"depth": 1})
        self.assertIn("cannot spawn", out)


class SandboxTest(unittest.TestCase):
    def test_sandbox_prefix_is_a_list(self):
        prefix = require(self, "sandbox_prefix")
        result = prefix(Path.cwd())
        self.assertIsInstance(result, list)
        if result:
            self.assertIn("--", result)


if __name__ == "__main__":
    unittest.main()
