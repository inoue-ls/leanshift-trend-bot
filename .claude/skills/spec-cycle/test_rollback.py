"""Exercise the rollback commands exactly as SKILL.md writes them.

Run (repo root): python3 -m unittest discover -s .claude/skills/spec-cycle -p 'test_*.py'

The rollback only runs when a cycle fails, so a successful cycle never
exercises it. This test pulls the rollback block out of SKILL.md, checks
guard-bash.py lets each line through on the pipeline branch, and runs it in a
throwaway repository.
"""

import importlib.util
import pathlib
import re
import subprocess
import tempfile
import unittest

HERE = pathlib.Path(__file__).parent
SKILL = HERE / "SKILL.md"
HOOK = HERE.parents[1] / "hooks" / "guard-bash.py"
_spec = importlib.util.spec_from_file_location("guard_bash", HOOK)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

TIMESTAMP = "20260930-120000"


def rollback_lines(base):
    blocks = re.findall(r"```bash\n(.*?)```", SKILL.read_text(encoding="utf-8"), re.DOTALL)
    block = next(b for b in blocks if "git tag vibe/failed/" in b)
    lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
    return [ln.replace("<timestamp>", TIMESTAMP).replace("<base>", base) for ln in lines]


class RollbackTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def git(self, *args):
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
            cwd=self.repo, check=True, capture_output=True, text=True,
        ).stdout.strip()

    def test_rollback_block_passes_the_guard_and_restores_base(self):
        self.git("init", "-q", "-b", "main")
        (self.repo / "a.txt").write_text("base\n")
        self.git("add", "a.txt")
        self.git("commit", "-q", "-m", "base")
        base = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "-b", "vibe/temp-feature")
        (self.repo / "spec.json").write_text("{}\n")
        self.git("add", "spec.json")
        self.git("commit", "-q", "-m", "spec")
        tip = self.git("rev-parse", "HEAD")
        (self.repo / "a.txt").write_text("half-done green\n")  # uncommitted edit
        (self.repo / "new.py").write_text("x = 1\n")  # untracked file

        lines = rollback_lines("main")
        self.assertEqual(len(lines), 2)
        for line in lines:
            with self.subTest(line=line):
                self.assertIsNone(guard.check(line, branch="vibe/temp-feature"))
        for line in lines:
            subprocess.run(["bash", "-c", line], cwd=self.repo, check=True, capture_output=True)

        self.assertEqual(self.git("branch", "--show-current"), "main")
        self.assertEqual(self.git("rev-parse", "HEAD"), base)
        self.assertEqual(self.git("branch", "--list", "vibe/temp-feature"), "")
        self.assertEqual(self.git("rev-parse", f"vibe/failed/{TIMESTAMP}"), tip)
        self.assertEqual(self.git("show", f"vibe/failed/{TIMESTAMP}:spec.json"), "{}")
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual((self.repo / "a.txt").read_text(), "base\n")
        self.assertFalse((self.repo / "new.py").exists())


if __name__ == "__main__":
    unittest.main()
