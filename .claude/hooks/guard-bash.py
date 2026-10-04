#!/usr/bin/env python3
"""PreToolUse guard for Bash tool calls.

Permission globs in settings.json only match a command *prefix*, so
`cd x && git reset --hard` slips past `Bash(git reset --hard *)`. This hook
inspects the whole command string and blocks dangerous patterns anywhere
in it.

Heredoc bodies and `-m` / `--message` values are stripped before matching,
so a commit message that merely mentions a blocked phrase does not trip the
guard. Other quoted arguments are kept, so `psql -c "DROP TABLE x"` is still
caught. Known trade-off: `echo "git reset --hard"` is a false positive.

Exit 2 => the tool call is blocked and stderr is shown to Claude.
Fails open (exit 0) on any parsing error.
"""

import json
import re
import sys


def strip_noise(cmd: str) -> str:
    # Drop heredoc bodies: <<[-] ['"]?WORD['"]? ... \nWORD
    cmd = re.sub(
        r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1.*?\n\2\b",
        " ",
        cmd,
        flags=re.DOTALL,
    )
    # Drop commit/message payloads: -m / --message  "<...>" | '<...>' | $(...) | word
    cmd = re.sub(
        r"(?:-m|--message)(?:\s+|=)(?:\"[^\"]*\"|'[^']*'|\$\([^)]*\)|\S+)",
        " -m MSG ",
        cmd,
    )
    return re.sub(r"\s+", " ", cmd).strip()


# Recursive rm is fine on a named relative path (node_modules, dist, ...).
# It is not fine on these targets.
_RM_DANGER_TARGETS = {"/", "~", "*", ".", "..", "/*", "~/", "~/*", "./*", "../*"}


def dangerous_rm(cmd: str) -> bool:
    for seg in re.split(r"\|\||&&|[|&;\n]", cmd):
        toks = seg.split()
        idx = next(
            (i for i, t in enumerate(toks) if t == "rm" or t.endswith("/rm")),
            None,
        )
        if idx is None:
            continue
        args = toks[idx + 1:]
        short_flags = "".join(
            a[1:] for a in args if a.startswith("-") and not a.startswith("--")
        )
        recursive = "r" in short_flags or "--recursive" in args
        if not recursive:
            continue
        targets = [a.strip("'\"") for a in args if not a.startswith("-")]
        if not targets:  # `rm -rf` with no path yet — treat as suspicious
            return True
        for t in targets:
            if (
                t in _RM_DANGER_TARGETS
                or t.startswith("/")            # any absolute path
                or t.startswith("~")            # home
                or re.match(r"^\$\{?\w+", t)    # unexpanded variable
                or t.endswith("/*")
                or t == "$HOME"
            ):
                return True
    return False


RULES = [
    (r"\bgit\s+push\s+([^|&;]*\s)?(--force(\b|[^-])|-f\b)", "forced git push"),
    (r"\bgit\s+reset\s+--hard\b", "git hard reset"),
    (r"\bgit\s+add\s+([^|&;]*\s)?(-A\b|--all\b|\.(?=\s|$|[|&;]))", "blanket git add (use git add -u plus explicit paths)"),
    (r"\bgit\s+add\s+([^|&;]*\s)?(-f\b|--force\b)", "forced git add (bypasses .gitignore)"),
    (r"\bgit\s+clean\s+([^|&;]*\s)?(-[a-zA-Z]*f|--force\b)", "forced git clean (deletes untracked files)"),
    (r"\bgit\s+checkout\s+([^|&;]*\s)?(-f\b|--force\b)", "forced git checkout (discards changes)"),
    (r"\bgit\s+switch\s+([^|&;]*\s)?(-f\b|--force\b|--discard-changes\b)", "git switch discarding changes"),
    # Only `git restore --staged` (index only) is safe; anything touching the worktree discards edits.
    (r"\bgit\s+restore\b(?![^|&;]*(--staged\b|\s(?-i:-S)\b))", "git restore of the working tree"),
    (r"\bgit\s+restore\b[^|&;]*(--worktree\b|\s(?-i:-W)\b)", "git restore of the working tree"),
    (r"\bgit\s+checkout\s+([^|&;]*\s)?(--(?=\s|$)|\.(?=\s|$|[|&;]))", "git checkout discarding working-tree changes"),
    (r"\bgit\s+stash\s+(drop|clear)\b", "discarding stashed work"),
    (r"\bgit\s+(update-ref|filter-branch|filter-repo|replace)\b", "rewriting git refs or history"),
    (r"\bgit\s+branch\s+([^|&;]*\s)?(-f\b|--force\b|(?-i:-M)\b|(?-i:-C)\b)", "force-moving a branch"),
    (r"\bgit\s+(checkout|switch)\s+([^|&;]*\s)?((?-i:-B)|(?-i:-C))\b", "resetting a branch with checkout -B / switch -C"),
    (r"\b(DROP|TRUNCATE)\s+(TABLE|DATABASE|SCHEMA)\b", "destructive SQL (DROP/TRUNCATE)"),
    (r"\bDELETE\s+FROM\s+[A-Za-z_.]+\s*(;|$)", "unscoped SQL DELETE"),
    (r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(sh|bash|zsh)\b", "piping a download into a shell"),
    (r"\b(cat|less|more|head|tail|xxd|base64|strings|grep|awk|sed)\s+[^|&;]*\.env\b", "reading .env through a shell"),
    (r"\b(curl|wget|nc|scp|rsync)\b[^|&;]*(\.env|id_rsa|\.aws|\.ssh|credentials)", "possible secret exfiltration"),
    (r"\bdd\s+[^|&;]*of=/dev/", "dd writing to a device"),
    (r":\(\)\s*\{\s*:", "fork bomb"),
    (r"\bmkfs\b", "filesystem format (mkfs)"),
    (r"\bchmod\s+(-R\s+)?0*777\b", "chmod 777"),
    (r">\s*/dev/(sd|nvme|hd)", "overwrite of a block device"),
]


def check(cmd: str):
    """Return the block reason for a command, or None if it is allowed."""
    scrubbed = strip_noise(cmd)
    if dangerous_rm(scrubbed):
        return "recursive rm on a broad/absolute path"
    for pat, why in RULES:
        if re.search(pat, scrubbed, re.IGNORECASE):
            return why
    return None


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if not cmd.strip():
        return 0

    reason = check(cmd)
    if reason:
        sys.stderr.write(f"guard-bash: BLOCKED — {reason}\n")
        sys.stderr.write(f"guard-bash: command was: {cmd}\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
