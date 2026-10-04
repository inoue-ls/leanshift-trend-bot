"""Tests for brief.py.

Run (repo root): python3 -m unittest discover -s .claude/skills/spec-cycle -p 'test_*.py'
"""

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).with_name("brief.py")

SPEC = {
    "runtime": {"language": "python 3", "test_command": "python3 -m unittest -v"},
    "target_increment": {"focus": "合計する", "source": "合計している", "acceptance_criteria": {"then": "350 を返す"}},
    "execution_steps": [
        {"step": 1, "name": "Red", "assertion": "RED-STEP", "scope": "tests"},
        {"step": 2, "name": "Green", "assertion": "GREEN-STEP", "scope": "code"},
        {"step": 3, "name": "Baseline", "assertion": "BASELINE-STEP", "scope": "spec.json"},
    ],
    "wont": ["GUI"],
    "assumptions": ["ヘッダーあり"],
    "current_baseline": {"test_status": "initial", "features": []},
    "pains": ["CSV の金額列を毎回手で合計している"],
}


class BriefTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        (self.root / "spec.json").write_text(json.dumps(SPEC, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def brief(self, *args, stdin=""):
        r = subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin, capture_output=True, text=True, cwd=self.root)
        return r.returncode, r.stdout, r.stderr

    def fields(self, out):
        return json.loads(out.split("```json\n", 1)[1].split("\n```", 1)[0])

    def test_builder_red_gets_spec_fields_verbatim_and_only_step_1(self):
        code, out, _ = self.brief("builder-red")
        self.assertEqual(code, 0)
        self.assertIn("Mode: Red", out)
        fields = self.fields(out)
        self.assertEqual(fields["target_increment"], SPEC["target_increment"])
        self.assertEqual(fields["execution_step"], SPEC["execution_steps"][0])
        self.assertEqual(fields["current_baseline.features"], [])
        self.assertEqual(set(fields), {"runtime", "target_increment", "execution_step", "wont", "assumptions", "current_baseline.features"})
        self.assertNotIn("GREEN-STEP", out)

    def test_builder_green_gets_step_2(self):
        code, out, _ = self.brief("builder-green")
        self.assertEqual(code, 0)
        self.assertIn("Mode: Green", out)
        self.assertEqual(self.fields(out)["execution_step"], SPEC["execution_steps"][1])
        self.assertNotIn("RED-STEP", out)

    def test_sentry_gets_only_iteration_and_base(self):
        code, out, _ = self.brief("sentry", "--iteration", "2", "--base", "abc123")
        self.assertEqual(code, 0)
        self.assertIn("Iteration: 2 / 3", out)
        self.assertIn("Base commit: abc123", out)
        self.assertNotIn("合計", out)  # no spec content: sentry reads spec.json itself

    def test_sentry_requires_iteration_and_base(self):
        code, _, err = self.brief("sentry")
        self.assertEqual(code, 2)
        self.assertIn("--iteration and --base", err)

    def test_planner_reads_the_pain_verbatim_from_stdin(self):
        pain = "請求書 CSV を \"毎月\" 手で作っているし、it's $HOME `date` も壊さない"
        code, out, _ = self.brief("planner", stdin=pain + "\n")  # a heredoc adds one trailing newline
        self.assertEqual(code, 0)
        self.assertIn(f"Pain (verbatim):\n{pain}\n\n", out)
        code, out, _ = self.brief("planner", stdin="")
        self.assertIn("Pain (verbatim):\n(none)", out)

    def test_unknown_role(self):
        code, _, err = self.brief("reviewer")
        self.assertEqual(code, 2)
        self.assertIn("invalid choice", err)


if __name__ == "__main__":
    unittest.main()
