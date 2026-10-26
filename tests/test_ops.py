"""Sessions, credential validation and uninstall behaviour."""

import argparse
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tests.harness import hr


def run(func, **kwargs):
    args = argparse.Namespace(**kwargs)
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = func(args)
    return code, buffer.getvalue()


class SessionsTest(unittest.TestCase):
    def setUp(self):
        self.session = hr.sessions_dir() / "unit-session.json"
        hr.sessions_dir().mkdir(parents=True, exist_ok=True)
        self.session.write_text(json.dumps({
            "version": 1, "model": "auto",
            "messages": [{"role": "user", "content": "hello"},
                         {"role": "assistant", "content": "hi there"}],
        }), encoding="utf-8")
        self.transcript = hr.transcript_dir(hr.load_config()) / "unit-transcript.jsonl"
        self.transcript.parent.mkdir(parents=True, exist_ok=True)
        self.transcript.write_text(
            json.dumps({"role": "user", "content": "logged question"}) + "\n", encoding="utf-8")

    def tearDown(self):
        self.session.unlink(missing_ok=True)
        self.transcript.unlink(missing_ok=True)

    def test_list_includes_sessions_and_transcripts(self):
        code, output = run(hr.cmd_sessions, action="list", name=None, json=True,
                           limit=20, days=30, output=None, yes=False, dry_run=False)
        self.assertEqual(code, 0)
        rows = json.loads(output)
        names = {row["name"]: row for row in rows}
        self.assertIn("unit-session", names)
        self.assertEqual(names["unit-session"]["messages"], 2)
        self.assertEqual(names["unit-session"]["model"], "auto")
        self.assertIn("unit-transcript", names)
        self.assertEqual(names["unit-transcript"]["kind"], "transcript")

    def test_show_prints_recent_messages(self):
        code, output = run(hr.cmd_sessions, action="show", name="unit-session", json=False,
                           limit=5, days=30, output=None, yes=False, dry_run=False)
        self.assertEqual(code, 0)
        self.assertIn("hi there", output)

    def test_export_writes_markdown(self):
        target = Path("exported-session.md")
        target.unlink(missing_ok=True)
        code, _ = run(hr.cmd_sessions, action="export", name="unit-session", json=False,
                      limit=20, days=30, output=str(target), yes=False, dry_run=False)
        self.assertEqual(code, 0)
        text = target.read_text(encoding="utf-8")
        self.assertIn("# hyperRouter session: unit-session", text)
        self.assertIn("hello", text)
        target.unlink()

    def test_delete_requires_yes(self):
        with self.assertRaises(SystemExit):
            run(hr.cmd_sessions, action="delete", name="unit-session", json=False,
                limit=20, days=30, output=None, yes=False, dry_run=False)
        self.assertTrue(self.session.exists())

    def test_resume_only_for_sessions(self):
        code, output = run(hr.cmd_sessions, action="resume", name="unit-session", json=False,
                           limit=20, days=30, output=None, yes=False, dry_run=False)
        self.assertEqual(code, 0)
        self.assertIn("--session", output)


class CredentialValidationTest(unittest.TestCase):
    def setUp(self):
        self._http = hr.http_json
        self._models_url = hr.models_url
        self._chat_url = hr.chat_url
        hr.models_url = lambda provider: f"https://{provider}.test/models"
        hr.chat_url = lambda provider: f"https://{provider}.test/chat/completions"

    def tearDown(self):
        hr.http_json = self._http
        hr.models_url = self._models_url
        hr.chat_url = self._chat_url

    def test_models_endpoint_success(self):
        hr.http_json = lambda *a, **k: (200, {}, {"data": [{"id": "m1"}, {"id": "m2"}]})
        ok, detail = hr.validate_provider_key("pollinations", "abc")
        self.assertTrue(ok, detail)
        self.assertIn("2 models", detail)

    def test_rejected_key_fails_without_retry(self):
        hr.http_json = lambda *a, **k: (401, {}, {"error": "bad key"})
        ok, detail = hr.validate_provider_key("pollinations", "abc")
        self.assertFalse(ok)
        self.assertIn("401", detail)

    def test_empty_key_is_refused(self):
        ok, detail = hr.validate_provider_key("pollinations", "")
        self.assertFalse(ok)
        self.assertIn("empty", detail)


class UninstallTest(unittest.TestCase):
    def test_dry_run_names_the_installed_files(self):
        code, output = run(hr.cmd_uninstall, purge=True, keep_service=False,
                           dry_run=True, yes=False)
        self.assertEqual(code, 0)
        self.assertIn("would remove", output)
        self.assertIn("hyperrouter", output)


if __name__ == "__main__":
    unittest.main()
