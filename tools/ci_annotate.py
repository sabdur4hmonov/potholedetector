#!/usr/bin/env python3
"""Turn a CI log into GitHub Actions error annotations.

Annotations are readable through the public check-runs API without a token, so a
failing run can be diagnosed without downloading job logs.

Usage:
  ci_annotate.py run-all <log>   summarize FAIL blocks printed by tests/run-all.sh
  ci_annotate.py plain <log> <title> [lines]   last N lines of a log as one annotation

The run-all mode also reads the Node test log, which uses the same "name   FAIL" plus
indented-output layout.

GitHub shows at most 10 error annotations per step, so the first annotation lists every
failing test by name and only the first few get a detail block.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_DETAIL = 7
MESSAGE_LIMIT = 3500


def escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def emit(title: str, message: str) -> None:
    if len(message) > MESSAGE_LIMIT:
        message = "..." + message[-MESSAGE_LIMIT:]
    print(f"::error title={escape(title)}::{escape(message)}")


def read(path: str) -> list[str]:
    return Path(path).read_text(encoding="utf-8", errors="replace").splitlines()


def run_all(lines: list[str]) -> int:
    failures: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None
    for line in lines:
        header = re.match(r"^(\S+)\s+(FAIL|SKIPPED.*)$", line)
        if header:
            current = (header.group(1), [])
            failures.append(current)
        elif current and line.startswith("    "):
            current[1].append(line.strip())
        else:
            current = None
    if not failures:
        return 0
    emit(f"{len(failures)} test(s) failed in run-all.sh", ", ".join(name for name, _ in failures))
    for name, detail in failures[:MAX_DETAIL]:
        emit(f"FAIL {name}", "\n".join(detail) or "(no output captured)")
    return len(failures)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    mode, log = argv[1], argv[2]
    lines = read(log)
    if mode == "run-all":
        run_all(lines)
    elif mode == "plain":
        title = argv[3] if len(argv) > 3 else "log tail"
        count = int(argv[4]) if len(argv) > 4 else 60
        emit(title, "\n".join(lines[-count:]))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
