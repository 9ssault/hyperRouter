"""Agent-loop behaviour that needs a deterministic route_once."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.harness import hr


def scripted_route(path="out.txt", content="x\n"):
    """A fake free pool: one write_file call, then a final answer."""

    def route(messages, **kwargs):
        if not any(message.get("role") == "tool" for message in messages):
            call = {"id": "c1", "type": "function",
                    "function": {"name": "write_file",
                                 "arguments": json.dumps({"path": path, "content": content})}}
            return {"choices": [{"message": {"content": "", "tool_calls": [call]}}],
                    "x_agent_router": {"provider": "fake", "model": "fake-1", "latency_ms": 1}}
        return {"choices": [{"message": {"content": "done"}}],
                "x_agent_router": {"provider": "fake", "model": "fake-1", "latency_ms": 1}}

    return route


class AgentLoopTest(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self._route = hr.route_once
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)

    def tearDown(self):
        hr.route_once = self._route
        os.chdir(self._cwd)
        self.tmp.cleanup()

    def messages(self):
        return [{"role": "system", "content": "test"},
                {"role": "user", "content": "write a file"}]

    def test_verification_runs_and_reports_success(self):
        Path("Makefile").write_text("test:\n\t@true\n", encoding="utf-8")
        hr.route_once = scripted_route()
        result = hr.agent_turn(self.messages(), max_rounds=2,
                               approve=lambda kind, detail, preview="": True,
                               ctx={"isolation": False})
        verification = result.get("verification") or {}
        self.assertEqual(verification.get("command"), "make test")
        self.assertTrue(verification.get("ok"), verification)
        self.assertTrue(Path("out.txt").is_file())

    def test_verification_reports_failure(self):
        Path("Makefile").write_text("test:\n\t@false\n", encoding="utf-8")
        hr.route_once = scripted_route()
        result = hr.agent_turn(self.messages(), max_rounds=2,
                               approve=lambda kind, detail, preview="": True,
                               ctx={"isolation": False})
        self.assertFalse((result.get("verification") or {}).get("ok"))

    def test_worker_merges_isolated_change(self):
        Path("target.txt").write_text("before\n", encoding="utf-8")
        hr.route_once = scripted_route("target.txt", "after\n")
        out = hr.tool_subagent({"tasks": [{"files": ["target.txt"], "task": "rewrite it"}]},
                               approve=lambda kind, detail, preview="": True,
                               ctx={"root": os.getcwd()})
        payload = json.loads(out)
        self.assertTrue(payload.get("isolated"))
        self.assertEqual(payload["workers"][0]["changed"], ["target.txt"])
        self.assertEqual(Path("target.txt").read_text(encoding="utf-8"), "after\n")

    def test_worker_conflict_leaves_original_alone(self):
        Path("target.txt").write_text("before\n", encoding="utf-8")
        hr.route_once = scripted_route("target.txt", "after\n")
        real = hr.run_subagent

        def racing(*args, **kwargs):
            report = real(*args, **kwargs)
            Path("target.txt").write_text("someone else\n", encoding="utf-8")
            return report

        hr.run_subagent = racing
        try:
            out = hr.tool_subagent({"tasks": [{"files": ["target.txt"], "task": "rewrite it"}]},
                                   approve=lambda kind, detail, preview="": True,
                                   ctx={"root": os.getcwd()})
        finally:
            hr.run_subagent = real
        payload = json.loads(out)
        self.assertEqual(payload["workers"][0]["conflicts"], ["target.txt"])
        self.assertEqual(Path("target.txt").read_text(encoding="utf-8"), "someone else\n")


if __name__ == "__main__":
    unittest.main()
