#!/usr/bin/env python3
"""Run ModpackTools-owned self tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent


def run(command: list[str]) -> int:
    print("", flush=True)
    print(f"=== {' '.join(command)} ===", flush=True)
    return subprocess.run(command, cwd=TOOLS_DIR).returncode


def compile_python_sources() -> int:
    return run([sys.executable, "-m", "compileall", "-q", "."])


def run_python_tests() -> int:
    for test_file in sorted(TESTS_DIR.glob("test_*.py")):
        result = run([sys.executable, str(test_file.relative_to(TOOLS_DIR))])
        if result != 0:
            return result
    return 0


def main() -> int:
    for step in (compile_python_sources, run_python_tests):
        result = step()
        if result != 0:
            return result
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
