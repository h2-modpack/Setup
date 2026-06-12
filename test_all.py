#!/usr/bin/env python3
"""Run the repo's Lua and Python test suites from one entrypoint."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
ROOT_DIR = TOOLS_DIR.parent


@dataclass(frozen=True)
class TestCommand:
    name: str
    cwd: Path
    command: list[str]


def find_lua_runner(explicit: str | None) -> str | None:
    if explicit:
        return explicit if is_lua52_runner(explicit) else None
    for candidate in lua_runner_candidates():
        resolved = shutil.which(candidate)
        if resolved and is_lua52_runner(resolved):
            return resolved
    return None


def lua_runner_candidates(os_name: str | None = None) -> tuple[str, ...]:
    current_os = os_name or os.name
    if current_os == "nt":
        return ("lua52.exe", "lua5.2", "lua52", "lua")
    return ("lua5.2", "lua52", "lua", "lua52.exe")


def is_lua52_runner(command: str) -> bool:
    try:
        result = subprocess.run(
            [command, "-e", "assert(_VERSION == 'Lua 5.2', _VERSION)"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def discover_lua_tests(lua_runner: str) -> list[TestCommand]:
    commands: list[TestCommand] = []
    for repo in (ROOT_DIR / "adamant-ModpackLib",):
        test_file = repo / "tests" / "all.lua"
        if test_file.is_file():
            commands.append(TestCommand(repo.name, repo, [lua_runner, "tests/all.lua"]))

    submodules_dir = ROOT_DIR / "Submodules"
    if submodules_dir.is_dir():
        for repo in sorted(path for path in submodules_dir.iterdir() if path.is_dir()):
            test_file = repo / "tests" / "all.lua"
            if test_file.is_file():
                commands.append(TestCommand(repo.name, repo, [lua_runner, "tests/all.lua"]))
            integration_file = repo / "tests" / "integration.lua"
            if integration_file.is_file():
                commands.append(TestCommand(f"{repo.name} integration", repo, [lua_runner, "tests/integration.lua"]))

    tools_tests_dir = TOOLS_DIR / "tests"
    if tools_tests_dir.is_dir():
        for test_file in sorted(tools_tests_dir.glob("test_*.lua")):
            commands.append(
                TestCommand(
                    f"ModpackTools/{test_file.name}",
                    ROOT_DIR,
                    [lua_runner, str(test_file.relative_to(ROOT_DIR))],
                )
            )
    return commands


def discover_python_tests() -> list[TestCommand]:
    tests_dir = TOOLS_DIR / "tests"
    if not tests_dir.is_dir():
        return []
    return [
        TestCommand(f"ModpackTools/{test_file.name}", ROOT_DIR, [sys.executable, str(test_file)])
        for test_file in sorted(tests_dir.glob("test_*.py"))
    ]


def run_commands(commands: list[TestCommand]) -> int:
    failures: list[str] = []
    for command in commands:
        print(f"\n=== {command.name} ===")
        result = subprocess.run(command.command, cwd=command.cwd)
        if result.returncode != 0:
            failures.append(command.name)

    print("\n=== Summary ===")
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1

    print(f"{len(commands)} passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lua", default=None, help="Lua 5.2 executable override")
    parser.add_argument("--python-only", action="store_true", help="Run only ModpackTools Python tests")
    args = parser.parse_args()

    commands = discover_python_tests()
    if not args.python_only:
        lua_runner = find_lua_runner(args.lua)
        if not lua_runner:
            print("Lua 5.2 runner not found. Install lua5.2/lua52/lua52.exe or pass --lua.", file=sys.stderr)
            return 2
        commands = discover_lua_tests(lua_runner) + commands

    if not commands:
        print("No tests discovered.")
        return 0
    return run_commands(commands)


if __name__ == "__main__":
    sys.exit(main())
