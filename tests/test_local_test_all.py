#!/usr/bin/env python3
"""Tests for local_test/all.py."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
LOCAL_TEST_ALL_PATH = TOOLS_DIR / "local_test" / "all.py"
spec = importlib.util.spec_from_file_location("local_test_all", LOCAL_TEST_ALL_PATH)
local_test_all = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["local_test_all"] = local_test_all
spec.loader.exec_module(local_test_all)


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def write_package(repo_dir: Path, namespace: str, name: str) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "thunderstore.toml").write_text(
        "\n".join(
            [
                "[package]",
                f'namespace = "{namespace}"',
                f'name = "{name}"',
                'versionNumber = "1.0.0"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def make_shell_files(root: Path) -> None:
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "smoke.lua").write_text("return true\n", encoding="utf-8")
    (root / ".gitmodules").write_text(
        """
[submodule "Submodules/team-ModuleA"]
    path = Submodules/team-ModuleA
    url = https://example.invalid/team-ModuleA.git
[submodule "Submodules/team-ModuleB"]
    path = Submodules/team-ModuleB
    url = https://example.invalid/team-ModuleB.git
[submodule "team-Pack_Modpack"]
    path = team-Pack_Modpack
    url = https://example.invalid/team-Pack_Modpack.git
""".lstrip(),
        encoding="utf-8",
    )
    write_package(root / "Submodules" / "team-ModuleA", "team", "ModuleA")
    write_package(root / "Submodules" / "team-ModuleB", "team", "ModuleB")
    write_package(root / "team-Pack_Modpack", "team", "Pack_Modpack")


def test_read_checkout_repos_uses_registered_submodules() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_shell_files(root)

        repos = local_test_all.read_checkout_repos(root)

    assert_equal(
        [(repo.name, repo.path.name) for repo in repos],
        [
            ("adamant-ModpackLib", "adamant-ModpackLib"),
            ("team-ModuleA", "team-ModuleA"),
            ("team-ModuleB", "team-ModuleB"),
            ("team-Pack_Modpack", "team-Pack_Modpack"),
        ],
        "checkout repos",
    )


def test_build_commands_runs_smoke_then_declared_repo_tests() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_shell_files(root)
        lib = root / "adamant-ModpackLib"
        module_a = root / "Submodules" / "team-ModuleA"
        (lib / "tests").mkdir(parents=True, exist_ok=True)
        (module_a / "tests").mkdir(parents=True)
        (lib / "tests" / "all.lua").write_text("", encoding="utf-8")
        (module_a / "tests" / "all.py").write_text("", encoding="utf-8")

        plan = local_test_all.build_plan(root, "lua52", "python3")
        commands = plan.commands

    assert_equal(
        [command.name for command in commands[:-1]],
        ["Shell smoke", "adamant-ModpackLib", "team-ModuleA"],
        "test command names",
    )
    assert_equal(commands[0].command, ["lua52", "tests/smoke.lua"], "smoke command")
    assert_equal(commands[1].command, ["lua52", "tests/all.lua"], "lua repo command")
    assert_equal(commands[2].command, ["python3", "tests/all.py"], "python repo command")
    assert_equal(commands[-1].name, "ModpackTools", "tools command")
    assert_equal(
        [(repo.name, repo.path.name) for repo in plan.skipped],
        [("team-ModuleB", "team-ModuleB"), ("team-Pack_Modpack", "team-Pack_Modpack")],
        "skipped repos",
    )


def test_build_commands_can_skip_smoke() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        make_shell_files(root)
        lib = root / "adamant-ModpackLib"
        (lib / "tests").mkdir(parents=True, exist_ok=True)
        (lib / "tests" / "all.lua").write_text("", encoding="utf-8")

        commands = local_test_all.build_commands(root, "lua52", "python3", skip_smoke=True)

    assert_equal(commands[0].name, "adamant-ModpackLib", "first command")


def main() -> int:
    tests = [
        test_read_checkout_repos_uses_registered_submodules,
        test_build_commands_runs_smoke_then_declared_repo_tests,
        test_build_commands_can_skip_smoke,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} local_test all tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
