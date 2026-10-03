"""Print the exact prompt for a /spec-cycle subagent (stdlib only).

Usage (repo root):
  python3 .claude/skills/spec-cycle/brief.py planner <<'SPEC_CYCLE_PAIN_EOF'   (pain on stdin, verbatim; empty = none)
  python3 .claude/skills/spec-cycle/brief.py builder-red | builder-green
  python3 .claude/skills/spec-cycle/brief.py sentry --iteration N --base HASH

The orchestrator passes this output to the Agent tool unchanged. Builders get
spec.json fields verbatim; sentry gets only iteration and base commit
(it reads spec.json itself). Nothing about how to implement or how to judge
is added here, so the orchestrator cannot steer the builder or the gate.
"""

import argparse
import json
import pathlib
import sys

ROLES = ["planner", "builder-red", "builder-green", "sentry"]


def builder(spec, mode):
    step = spec["execution_steps"][0 if mode == "Red" else 1]
    fields = {
        "runtime": spec["runtime"],
        "target_increment": spec["target_increment"],
        "execution_step": step,
        "wont": spec["wont"],
        "assumptions": spec["assumptions"],
        "current_baseline.features": spec["current_baseline"]["features"],
    }
    return (
        f"Mode: {mode}\n"
        f"Repository root: {pathlib.Path.cwd()}\n\n"
        "spec.json fields (verbatim):\n"
        f"```json\n{json.dumps(fields, ensure_ascii=False, indent=2)}\n```\n\n"
        f"Follow your {mode} mode directives in .claude/agents/builder.md and report in its output format.\n"
    )


def sentry(iteration, base):
    return (
        f"Iteration: {iteration} / 3\n"
        f"Base commit: {base}\n"
        f"Repository root: {pathlib.Path.cwd()}\n\n"
        f"Apply your gates in .claude/agents/sentry.md against the base commit and report in its output format.\n"
    )


def planner(pain):
    return (
        f"Repository root: {pathlib.Path.cwd()}\n\n"
        f"Pain (verbatim):\n{pain if pain else '(none)'}\n\n"
        "Follow .claude/agents/planner.md and report in its output format.\n"
    )


def main(argv):
    parser = argparse.ArgumentParser(description="Print a /spec-cycle subagent prompt")
    parser.add_argument("role", choices=ROLES)
    parser.add_argument("--iteration", type=int)
    parser.add_argument("--base")
    args = parser.parse_args(argv[1:])

    if args.role == "planner":
        # stdin, not an argument: a pain with quotes, $ or backticks must reach the planner unchanged.
        pain = sys.stdin.read()
        print(planner(pain[:-1] if pain.endswith("\n") else pain), end="")
        return 0
    if args.role == "sentry":
        if args.iteration is None or not args.base:
            parser.error("sentry roles need --iteration and --base")
        print(sentry(args.iteration, args.base), end="")
        return 0
    spec = json.loads(pathlib.Path("spec.json").read_text(encoding="utf-8"))
    print(builder(spec, "Red" if args.role == "builder-red" else "Green"), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
