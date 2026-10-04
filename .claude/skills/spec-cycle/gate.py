"""Mechanical checks for the /spec-cycle orchestrator (stdlib only).

Usage (repo root):
  gate.py preflight [--pain]              Step 0. Prints "OK <base branch>" or "STOP: <reason>".
  gate.py snapshot                        Hash of the tracked diff plus untracked file contents.
  gate.py verify-unchanged --snapshot H   HALT if the tree changed since `snapshot` printed H.
  gate.py verify-head --expect HASH       HALT unless on vibe/temp-feature at HASH.
  gate.py verify-clean                    HALT unless the tree is clean (run right after each commit,
                                          so nothing the cycle made is left out of it).
  gate.py verify-planner --expect HASH    HALT unless HEAD is still HASH and the planner changed only
                                          spec.json / .gitignore.
  gate.py verify-commands                 HALT unless every runtime command in spec.json may run: a
                                          single command matching permissions.allow in .claude/settings*.json.
  gate.py baseline                        B-0. From Cycle 2: run setup_command (tree must stay clean)
                                          and require the existing tests to pass.
  gate.py verify-evidence --phase red|green --since SPEC [--until RED] TEST...
                                          Each TEST (bare test function name, e.g. test_total) must be
                                          in lines added since SPEC (up to RED, or the working tree).
                                          Then reinstall dependencies with setup_command (the tree must
                                          not change), re-run runtime.test_command, and HALT unless the
                                          exit code and each named test's result match the phase. In
                                          red, a test reported as an error (not an assertion) is rejected.

Commands taken from spec.json run inside this script, so neither Claude Code's
permission prompt nor the PreToolUse hook sees them. Before running one, this
script requires what a prompt would: a single command (no ;, &&, |, backticks,
$(, redirection) that matches permissions.allow and no deny rule in
.claude/settings.json / settings.local.json, and that guard-bash.py allows.

Exit 0 = OK, 1 = STOP / HALT (reason on stdout), 2 = bad usage. The skill calls
these instead of doing the checks by hand, so a check cannot be skipped quietly.
"""

import argparse
import fnmatch
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

PIPELINE_BRANCH = "vibe/temp-feature"
TEMPLATE_MARKER = pathlib.Path("setup/gen_apply_doc.py")
PLANNER_FILES = {"spec.json", ".gitignore"}
# Runner output differs: unittest prints "... FAIL" / "... ERROR", others print ✗ or "failed".
# ERROR (an exception, not an assertion) is only recognisable where the runner reports it separately.
RED_MARK = re.compile(r"\b(FAIL|FAILED)\b|✗|×", re.IGNORECASE)
ERROR_MARK = re.compile(r"\bERROR\b")
SHELL_OPERATORS = re.compile(r"[;&|`<>\n]|\$\(")
RUNTIME_COMMANDS = ["setup_command", "test_command", "format_command"]
GREEN_MARK = re.compile(r"\b(ok|PASS|PASSED)\b|✓", re.IGNORECASE)

_guard_path = pathlib.Path(__file__).resolve().parents[2] / "hooks" / "guard-bash.py"
_spec = importlib.util.spec_from_file_location("guard_bash", _guard_path)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def git(*args, check=True):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r


def preflight(pain_given):
    if TEMPLATE_MARKER.exists():
        return "STOP: this is the template repository; apply the pipeline to a product repository with setup/apply-spec-cycle.md and run it there"
    if git("status", "--porcelain").stdout.strip():
        return "STOP: commit か stash してから再実行してください"
    base = git("branch", "--show-current").stdout.strip()
    if not base:
        return "STOP: ブランチをチェックアウトしてから再実行してください"
    if base == PIPELINE_BRANCH:
        # Rolling back would check out and then delete the branch it returns to.
        return f"STOP: {PIPELINE_BRANCH} の上では開始できません。マージ先のブランチ（例: main）に移ってから再実行してください"
    spec_path = pathlib.Path("spec.json")
    if not pain_given:
        if not spec_path.exists():
            return "STOP: 初回は現場ペインを1行渡してください"
        if not json.loads(spec_path.read_text(encoding="utf-8")).get("next_sprint_backlog"):
            return "STOP: バックログが空です。新しいペインを渡してください"
    if git("rev-parse", "--verify", "--quiet", PIPELINE_BRANCH, check=False).returncode == 0:
        if git("merge-base", "--is-ancestor", PIPELINE_BRANCH, "HEAD", check=False).returncode != 0:
            return "STOP: 前回の vibe/temp-feature をマージしてから再実行してください"
    return f"OK {base}"


def snapshot():
    h = hashlib.sha1(git("diff", "HEAD").stdout.encode())
    untracked = [p for p in git("ls-files", "-o", "--exclude-standard", "-z").stdout.split("\0") if p]
    for path in sorted(untracked):
        h.update(path.encode() + b"\0" + hashlib.sha1(pathlib.Path(path).read_bytes()).digest())
    return h.hexdigest()


def verify_head(expect):
    branch = git("branch", "--show-current").stdout.strip()
    if branch != PIPELINE_BRANCH:
        return f"HALT tampering: not on {PIPELINE_BRANCH} (on '{branch}')"
    head = git("rev-parse", "HEAD").stdout.strip()
    if head != expect:
        return f"HALT tampering: HEAD is {head}, expected {expect}"
    return "OK"


def changed_paths():
    """Paths git status reports (tracked changes and untracked files), unquoted."""
    fields = git("status", "--porcelain", "-z", "--untracked-files=all").stdout.split("\0")
    paths, i = [], 0
    while i < len(fields):
        entry = fields[i]
        if entry:
            paths.append(entry[3:])
            if entry[0] in "RC":
                i += 1  # a rename or copy is followed by its original path
        i += 1
    return paths


def verify_clean():
    left = changed_paths()
    if left:
        return f"HALT uncommitted: not in the commit: {', '.join(sorted(left))}"
    return "OK"


def verify_planner(expect):
    head = git("rev-parse", "HEAD").stdout.strip()
    if head != expect:
        return f"HALT planner: HEAD moved to {head} (expected {expect}); the planner must not commit"
    changed = set(changed_paths())
    if "spec.json" not in changed:
        return "HALT planner: spec.json was not written"
    extra = sorted(changed - PLANNER_FILES)
    if extra:
        return f"HALT planner: planner changed files other than spec.json / .gitignore: {', '.join(extra)}"
    return "OK"


def load_spec():
    return json.loads(pathlib.Path("spec.json").read_text(encoding="utf-8"))


def permission_rules():
    allow, deny = [], []
    for name in ("settings.json", "settings.local.json"):
        path = pathlib.Path(".claude") / name
        if not path.exists():
            continue
        try:
            perms = json.loads(path.read_text(encoding="utf-8")).get("permissions", {})
        except json.JSONDecodeError:
            continue
        allow += perms.get("allow", [])
        deny += perms.get("deny", [])
    return allow, deny


def rule_matches(rule, command):
    """Claude Code's Bash rule forms: exact, `prefix *` (also legacy `prefix:*`), and globs."""
    m = re.fullmatch(r"Bash\((.*)\)", rule, re.DOTALL)
    if not m:
        return False
    pattern = m.group(1)
    if pattern.endswith(":*"):
        pattern = pattern[:-2] + " *"
    if pattern.endswith(" *") and "*" not in pattern[:-2]:
        prefix = pattern[:-2]
        return command == prefix or command.startswith(prefix + " ")
    if "*" in pattern:
        return fnmatch.fnmatchcase(command, pattern)
    return command == pattern


def permission_problem(command):
    """Why this command may not run unattended, or None. Mirrors what a permission prompt would stop."""
    if SHELL_OPERATORS.search(command):
        return f"'{command}' is not a single command (no ;, &&, |, backticks, $(, redirection)"
    allow, deny = permission_rules()
    if any(rule_matches(r, command) for r in deny):
        return f"'{command}' is denied in .claude/settings*.json"
    if not any(rule_matches(r, command) for r in allow):
        return f"'{command}' is not in permissions.allow"
    return None


def run_guarded(command):
    """Run a spec.json command only if a human allowed it and the Bash hook would. Returns (reason, result)."""
    problem = permission_problem(command)
    if problem:
        return f"HALT permission: {problem}", None
    reason = guard.check(command, PIPELINE_BRANCH)
    if reason:
        return f"HALT security: guard-bash blocks '{command}' ({reason})", None
    return None, subprocess.run(command, shell=True, capture_output=True, text=True)


def verify_commands():
    runtime = load_spec()["runtime"]
    missing, other = [], []
    for key in RUNTIME_COMMANDS:
        command = runtime.get(key, "")
        if not command:
            continue
        problem = permission_problem(command)
        if problem and problem.endswith("is not in permissions.allow"):
            missing.append(json.dumps(f"Bash({command})", ensure_ascii=False))
        elif problem:
            other.append(f"{key}: {problem}")
        elif guard.check(command, PIPELINE_BRANCH):
            other.append(f"{key}: guard-bash blocks '{command}'")
    if other:
        return "HALT permission: " + "; ".join(other)
    if missing:
        return ("HALT permission: a human must add to .claude/settings.json permissions.allow, then re-run: "
                + ", ".join(missing))
    return "OK"


def added_text(since, until):
    """Lines added since `since` (up to `until`, or in the working tree including untracked files)."""
    diff = git("diff", since, until).stdout if until else git("diff", since).stdout
    lines = [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    if not until:
        for path in changed_paths():
            p = pathlib.Path(path)
            if p.is_file() and git("ls-files", "--error-unmatch", path, check=False).returncode != 0:
                lines += p.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines)


def baseline():
    spec_path = pathlib.Path("spec.json")
    if not spec_path.exists() or not load_spec()["current_baseline"]["features"]:
        return "OK cycle 1: no baseline yet"
    runtime = load_spec()["runtime"]
    if runtime.get("setup_command"):
        halt, r = run_guarded(runtime["setup_command"])
        if halt:
            return halt
        if r.returncode != 0:
            return f"HALT setup: setup_command exited {r.returncode}"
        if git("status", "--porcelain").stdout.strip():
            return "HALT setup: setup_command changed the working tree (lockfile drift?)"
    halt, r = run_guarded(runtime["test_command"])
    if halt:
        return halt
    if r.returncode != 0:
        return f"HALT baseline: existing tests fail before any change (exit {r.returncode})"
    return "OK"


def verify_evidence(phase, since, until, tests):
    added = added_text(since, until)
    for name in tests:
        if not re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", added):
            return f"HALT evidence: {name} was not added in this cycle's tests (since {since})"
    runtime = load_spec()["runtime"]
    if runtime.get("setup_command"):
        # Ignored files (node_modules, venvs) are invisible to every diff; reinstall them from the lockfile.
        before = snapshot()
        halt, r = run_guarded(runtime["setup_command"])
        if halt:
            return halt
        if r.returncode != 0:
            return f"HALT setup: setup_command exited {r.returncode}"
        if snapshot() != before:
            return "HALT setup: setup_command changed the working tree (lockfile drift?)"
    halt, r = run_guarded(runtime["test_command"])
    if halt:
        return halt
    out = (r.stdout + r.stderr).splitlines()
    if phase == "red" and r.returncode == 0:
        return "HALT evidence: red phase but test_command succeeded"
    if phase == "green" and r.returncode != 0:
        return f"HALT evidence: green phase but test_command exited {r.returncode}"
    mark = RED_MARK if phase == "red" else GREEN_MARK
    for name in tests:
        word = re.compile(rf"(?<![\w]){re.escape(name)}(?![\w])")
        lines = [ln for ln in out if word.search(ln)]
        if not lines:
            return f"HALT evidence: {name} does not appear in the test output"
        if phase == "red" and any(ERROR_MARK.search(ln) for ln in lines):
            return f"HALT evidence: {name} failed with an error, not an assertion"
        if not any(mark.search(ln) for ln in lines):
            return f"HALT evidence: {name} is not reported as {'failing' if phase == 'red' else 'passing'}"
    return "OK"


def main(argv):
    parser = argparse.ArgumentParser(description="Mechanical checks for /spec-cycle")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preflight")
    p.add_argument("--pain", action="store_true", help="a pain was passed to /spec-cycle")
    sub.add_parser("snapshot")
    p = sub.add_parser("verify-unchanged")
    p.add_argument("--snapshot", required=True)
    p = sub.add_parser("verify-head")
    p.add_argument("--expect", required=True)
    sub.add_parser("verify-clean")
    p = sub.add_parser("verify-planner")
    p.add_argument("--expect", required=True, help="HEAD recorded right after creating vibe/temp-feature")
    sub.add_parser("verify-commands")
    sub.add_parser("baseline")
    p = sub.add_parser("verify-evidence")
    p.add_argument("--phase", choices=["red", "green"], required=True)
    p.add_argument("--since", required=True, help="the spec commit")
    p.add_argument("--until", help="the Red commit (green phase); omit to include the working tree")
    p.add_argument("tests", nargs="+", help="names of the tests added in this cycle")
    args = parser.parse_args(argv[1:])

    if args.cmd == "snapshot":
        print(snapshot())
        return 0
    if args.cmd == "preflight":
        result = preflight(args.pain)
    elif args.cmd == "verify-unchanged":
        result = "OK" if snapshot() == args.snapshot else "HALT tampering: the working tree changed while sentry ran"
    elif args.cmd == "verify-head":
        result = verify_head(args.expect)
    elif args.cmd == "verify-clean":
        result = verify_clean()
    elif args.cmd == "verify-planner":
        result = verify_planner(args.expect)
    elif args.cmd == "verify-commands":
        result = verify_commands()
    elif args.cmd == "baseline":
        result = baseline()
    else:
        result = verify_evidence(args.phase, args.since, args.until, args.tests)
    print(result)
    return 0 if result.startswith("OK") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
