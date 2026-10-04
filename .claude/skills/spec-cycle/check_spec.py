"""Validate spec.json (stdlib only).

Usage (repo root):
  python3 .claude/skills/spec-cycle/check_spec.py spec.json [--against REF]

Checks the schema (spec-schema.json), status-dependent rules, that everything
to be built quotes a recorded pain verbatim, and that every completed feature
points at real code. With --against, also checks the change from
`REF:spec.json` (e.g. HEAD) keeps the invariants: runtime frozen after Cycle 1,
pains / features / dropped_backlog append-only, at most one new dependency and
one new pain per cycle, wont lifted only by a new pain containing the item's keyword, and
backlog items leaving only through dropped_backlog (or completion).
Exit 0 = valid. Exit 1 = one error per line on stdout.
"""

import argparse
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

SCHEMA = pathlib.Path(__file__).with_name("spec-schema.json")
TYPES = {"object": dict, "array": list, "string": str, "integer": int}
FROZEN_RUNTIME = ["language", "setup_command", "test_command", "format_command", "test_file_convention"]
PATH = re.compile(r"^[\w./-]+$")
COMMANDS = ["setup_command", "test_command", "format_command"]

_guard_path = pathlib.Path(__file__).resolve().parents[2] / "hooks" / "guard-bash.py"
_spec = importlib.util.spec_from_file_location("guard_bash", _guard_path)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def _overlap(a, b):
    return a in b or b in a


def validate(value, schema, path="$"):
    """Subset of JSON Schema: type, enum, required, properties, additionalProperties, items, minLength."""
    t = schema.get("type")
    if t and (not isinstance(value, TYPES[t]) or (t == "integer" and isinstance(value, bool))):
        return [f"{path}: expected {t}"]
    errors = []
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: must be one of {schema['enum']}")
    if t == "string" and len(value.strip()) < schema.get("minLength", 0):
        errors.append(f"{path}: must not be empty")
    if t == "object":
        props = schema.get("properties", {})
        errors += [f"{path}: missing '{k}'" for k in schema.get("required", []) if k not in value]
        if schema.get("additionalProperties") is False:
            errors += [f"{path}: unexpected '{k}'" for k in value if k not in props]
        for k, sub in props.items():
            if k in value:
                errors += validate(value[k], sub, f"{path}.{k}")
    if t == "array":
        for i, item in enumerate(value):
            errors += validate(item, schema.get("items", {}), f"{path}[{i}]")
    return errors


def check(spec, root="."):
    errors = validate(spec, json.loads(SCHEMA.read_text(encoding="utf-8")))
    if errors:
        return errors

    for k in COMMANDS:
        reason = spec["runtime"][k] and guard.check(spec["runtime"][k], "vibe/temp-feature")
        if reason:
            errors.append(f"$.runtime.{k}: blocked by guard-bash ({reason})")

    pains = spec["pains"]
    if not pains:
        errors.append("$.pains: must not be empty")

    def quoted(source):
        return any(source in p for p in pains)

    ti = spec["target_increment"]
    increment = {"$.target_increment.focus": ti["focus"], "$.target_increment.source": ti["source"]}
    increment.update(
        {f"$.target_increment.acceptance_criteria.{k}": v for k, v in ti["acceptance_criteria"].items()}
    )
    baseline = spec["current_baseline"]
    features = baseline["features"]

    if spec["status"] == "ready_for_implementation":
        errors += [f"{k}: must not be empty" for k, v in increment.items() if not v.strip()]
        if ti["source"].strip() and not quoted(ti["source"]):
            errors.append("$.target_increment.source: not a verbatim quote from pains")
        if len(spec["execution_steps"]) != 3:
            errors.append("$.execution_steps: must have exactly 3 steps")
        if spec["cycle_type"] == "cycle_1_tracer":
            if features:
                errors.append("$.current_baseline.features: cycle_1_tracer must start with no features")
            if baseline["test_status"] != "initial":
                errors.append("$.current_baseline.test_status: must be 'initial' for cycle_1_tracer")
        else:
            if not features:
                errors.append("$.current_baseline.features: cycle_n_expansion needs at least one completed feature")
            if baseline["test_status"] != "all_green":
                errors.append("$.current_baseline.test_status: must be 'all_green' for cycle_n_expansion")
    else:
        increment["$.target_increment.extension_point"] = ti["extension_point"]
        errors += [f"{k}: must be cleared after completion" for k, v in increment.items() if v]
        if baseline["test_status"] != "all_green":
            errors.append("$.current_baseline.test_status: must be 'all_green' after completion")
        if spec["execution_steps"]:
            errors.append("$.execution_steps: must be empty after completion")

    for key in ("next_sprint_backlog", "dropped_backlog"):
        errors += [
            f"$.{key}[{i}].source: not a verbatim quote from pains"
            for i, b in enumerate(spec[key])
            if not quoted(b["source"])
        ]

    # A pain phrase backs one increment only; quoting the whole pain again must not reopen it.
    used = [f["source"] for f in features]
    backlog = [(f"$.next_sprint_backlog[{i}].source", b["source"]) for i, b in enumerate(spec["next_sprint_backlog"])]
    candidates = backlog[:]
    if spec["status"] == "ready_for_implementation" and ti["source"].strip():
        candidates.insert(0, ("$.target_increment.source", ti["source"]))
    for key, src in candidates:
        if any(_overlap(src, u) for u in used):
            errors.append(f"{key}: overlaps a source already used by a completed feature")
    for i, (key, src) in enumerate(candidates):
        is_target = key == "$.target_increment.source"
        for other_key, other in candidates[i + 1:]:
            if is_target and src == other:
                continue  # the promoted item stays in the backlog until completion
            if _overlap(src, other):
                errors.append(f"{key}: overlaps {other_key}" if is_target else f"{other_key}: overlaps {key}")

    for i, step in enumerate(spec["execution_steps"]):
        if not all(PATH.match(p.strip()) for p in step["scope"].split(",")):
            errors.append(f"$.execution_steps[{i}].scope: list file paths only (comma-separated)")

    root = pathlib.Path(root)
    for i, f in enumerate(features):
        path = root / f["file"]
        if not path.is_file():
            errors.append(f"$.current_baseline.features[{i}].file: {f['file']} does not exist")
        elif not re.search(rf"\b{re.escape(f['symbol'])}\b", path.read_text(encoding="utf-8", errors="replace")):
            errors.append(f"$.current_baseline.features[{i}].symbol: '{f['symbol']}' not found in {f['file']}")
    return errors


def _is_subsequence(short, long):
    it = iter(long)
    return all(x in it for x in short)


def check_transition(prev, new):
    """Invariants between the previous spec (None if there is none) and the new one."""
    if prev is None:
        if new["status"] != "ready_for_implementation" or new["cycle_type"] != "cycle_1_tracer":
            return ["no previous spec.json: expected a ready cycle_1_tracer"]
        if len(new["pains"]) != 1:
            return ["$.pains: the first spec records exactly one pain"]
        return []

    pr, nr = prev["runtime"], new["runtime"]
    pf, nf = prev["current_baseline"]["features"], new["current_baseline"]["features"]
    errors = [f"$.runtime.{k}: changed after Cycle 1" for k in FROZEN_RUNTIME if pr[k] != nr[k]]
    pp, np_ = prev["pains"], new["pains"]
    pdrop, ndrop = prev["dropped_backlog"], new["dropped_backlog"]
    if np_[: len(pp)] != pp:
        errors.append("$.pains: existing entries must be kept")

    if prev["status"] == "completed" and new["status"] == "ready_for_implementation":  # Phase A
        pd, nd = pr["dependencies"], nr["dependencies"]
        if nd[: len(pd)] != pd:
            errors.append("$.runtime.dependencies: existing entries must be kept in order")
        elif len(nd) - len(pd) > 1:
            errors.append("$.runtime.dependencies: at most one may be added per cycle")
        if any(h not in nr["harness_files"] for h in pr["harness_files"]):
            errors.append("$.runtime.harness_files: existing entries must be kept")
        if nf != pf:
            errors.append("$.current_baseline.features: Phase A must not change completed features")
        backlog = new["next_sprint_backlog"]
        if not backlog or backlog[0]["source"] != new["target_increment"]["source"]:
            # The promoted item stays in the backlog until completion, so it must be the head.
            errors.append("$.target_increment.source: must be the first item of next_sprint_backlog")
        new_pains = np_[len(pp):]
        if len(new_pains) > 1:
            errors.append("$.pains: at most one pain may be added per cycle")
        errors += [
            f"$.wont: '{w['item']}' removed without a new pain containing its keyword '{w['keyword']}'"
            for w in prev["wont"]
            if w not in new["wont"] and not any(w["keyword"] in p for p in new_pains)
        ]
        if ndrop[: len(pdrop)] != pdrop:
            errors.append("$.dropped_backlog: existing entries must be kept")
        kept = {b["item"] for b in new["next_sprint_backlog"]}
        dropped_now = {d["item"] for d in ndrop[len(pdrop):]}
        errors += [
            f"$.next_sprint_backlog: '{b['item']}' removed without a dropped_backlog entry"
            for b in prev["next_sprint_backlog"]
            if b["item"] not in kept and b["item"] not in dropped_now
        ]
    elif prev["status"] == "ready_for_implementation" and new["status"] == "completed":  # B-3
        errors += [f"$.runtime.{k}: must not change at completion" for k in ("dependencies", "harness_files") if pr[k] != nr[k]]
        if len(nf) != len(pf) + 1 or nf[: len(pf)] != pf:
            errors.append("$.current_baseline.features: must append exactly one feature and keep the rest")
        elif nf[-1]["source"] != prev["target_increment"]["source"]:
            errors.append(f"$.current_baseline.features[{len(nf) - 1}].source: must be the completed increment's source")
        errors += [
            f"$.{k}: must not change at completion"
            for k in ("cycle_type", "feature_name", "pains", "assumptions", "wont", "dropped_backlog", "proposals")
            if prev[k] != new[k]
        ]
        pb, nb = prev["next_sprint_backlog"], new["next_sprint_backlog"]
        if len(pb) - len(nb) not in (0, 1) or not _is_subsequence(nb, pb):
            errors.append("$.next_sprint_backlog: may only drop the completed item")
    else:
        errors.append(f"unexpected transition: {prev['status']} -> {new['status']}")
    return errors


def load_at(ref, path):
    """spec.json as committed at `ref`, or None if it does not exist there."""
    r = subprocess.run(["git", "show", f"{ref}:./{pathlib.Path(path).as_posix()}"], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 else None


def main(argv):
    parser = argparse.ArgumentParser(description="Validate spec.json")
    parser.add_argument("spec")
    parser.add_argument("--against", metavar="REF", help="also check invariants against REF:spec.json")
    args = parser.parse_args(argv[1:])
    try:
        spec = json.loads(pathlib.Path(args.spec).read_text(encoding="utf-8"))
        prev = load_at(args.against, args.spec) if args.against else None
    except (OSError, json.JSONDecodeError) as e:
        print(f"{args.spec}: {e}")
        return 1
    errors = check(spec)
    if not errors and args.against:
        errors = check_transition(prev, spec)
    for e in errors:
        print(e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
