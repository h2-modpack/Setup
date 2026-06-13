#!/usr/bin/env python3
"""Run local assembled-checkout tests from the registered shell composition."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = TOOLS_DIR.parent
NEW_MODULE_DIR = TOOLS_DIR / "new_module"
DEFAULT_SMOKE_SCRIPT = Path("tests/smoke.lua")

if str(NEW_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(NEW_MODULE_DIR))

import module_roster  # noqa: E402


@dataclass(frozen=True)
class RepoEntry:
    name: str
    path: Path


@dataclass(frozen=True)
class TestCommand:
    name: str
    cwd: Path
    command: list[str]


@dataclass(frozen=True)
class TestPlan:
    commands: list[TestCommand]
    skipped: list[RepoEntry]


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"{label} not found: {path}")


def read_checkout_repos(root_dir: Path) -> list[RepoEntry]:
    repos = [RepoEntry("adamant-ModpackLib", root_dir / "adamant-ModpackLib")]
    for module in module_roster.discover_module_repos(root_dir):
        repos.append(RepoEntry(module.dependency_id, module.path))

    coordinator = module_roster.find_coordinator_package(root_dir)
    if coordinator is not None:
        repos.append(RepoEntry(coordinator.package.thunderstore_id, coordinator.path))
    return repos


def test_command_for_repo(
    name: str,
    repo_dir: Path,
    lua_runner: str,
    python_runner: str,
) -> TestCommand | None:
    lua_test = repo_dir / "tests" / "all.lua"
    if lua_test.is_file():
        return TestCommand(name, repo_dir, [lua_runner, "tests/all.lua"])

    python_test = repo_dir / "tests" / "all.py"
    if python_test.is_file():
        return TestCommand(name, repo_dir, [python_runner, "tests/all.py"])

    return None


def add_repo_test_if_present(
    commands: list[TestCommand],
    skipped: list[RepoEntry],
    name: str,
    repo_dir: Path,
    lua_runner: str,
    python_runner: str,
) -> None:
    command = test_command_for_repo(name, repo_dir, lua_runner, python_runner)
    if command is not None:
        commands.append(command)
    else:
        skipped.append(RepoEntry(name, repo_dir))


def build_plan(
    root_dir: Path,
    lua_runner: str,
    python_runner: str,
    skip_smoke: bool = False,
) -> TestPlan:
    commands: list[TestCommand] = []
    skipped: list[RepoEntry] = []
    if not skip_smoke:
        require_file(root_dir / DEFAULT_SMOKE_SCRIPT, "shell smoke script")
        commands.append(
            TestCommand(
                "Shell smoke",
                root_dir,
                [lua_runner, str(DEFAULT_SMOKE_SCRIPT)],
            )
        )

    seen: set[Path] = set()
    for repo in read_checkout_repos(root_dir):
        repo_path = repo.path.resolve()
        if repo_path in seen:
            continue
        seen.add(repo_path)
        add_repo_test_if_present(commands, skipped, repo.name, repo_path, lua_runner, python_runner)

    add_repo_test_if_present(commands, skipped, "ModpackTools", TOOLS_DIR, lua_runner, python_runner)
    return TestPlan(commands, skipped)


def build_commands(
    root_dir: Path,
    lua_runner: str,
    python_runner: str,
    skip_smoke: bool = False,
) -> list[TestCommand]:
    return build_plan(root_dir, lua_runner, python_runner, skip_smoke).commands


def run_plan(plan: TestPlan, run=subprocess.run) -> int:
    failures: list[str] = []
    for command in plan.commands:
        print("", flush=True)
        print(f"=== {command.name} ===", flush=True)
        result = run(command.command, cwd=command.cwd)
        if result.returncode != 0:
            failures.append(command.name)

    if plan.skipped:
        print("", flush=True)
        print("=== Skipped: no tests/all.lua or tests/all.py ===", flush=True)
        for repo in plan.skipped:
            print(f"- {repo.name}: {repo.path}", flush=True)

    print("", flush=True)
    print("=== Summary ===", flush=True)
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}", flush=True)
        return 1

    if plan.skipped:
        print(f"{len(plan.commands)} passed, {len(plan.skipped)} skipped.", flush=True)
    else:
        print(f"{len(plan.commands)} passed.", flush=True)
    return 0


def run_commands(commands: list[TestCommand], run=subprocess.run) -> int:
    return run_plan(TestPlan(commands, []), run=run)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-smoke", action="store_true", help="Skip the shell smoke step")
    parser.add_argument("--lua", default="lua", help="Lua runner (default: lua)")
    parser.add_argument("--python", default=sys.executable, help="Python runner for tests/all.py files")
    args = parser.parse_args(argv)

    try:
        plan = build_plan(ROOT_DIR, args.lua, args.python, args.skip_smoke)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not plan.commands:
        print("No tests discovered.")
        if plan.skipped:
            print("Skipped repos without tests/all.lua or tests/all.py:")
            for repo in plan.skipped:
                print(f"- {repo.name}: {repo.path}")
        return 0
    return run_plan(plan)


if __name__ == "__main__":
    sys.exit(main())
