#!/usr/bin/env python3
"""Tests for ModpackTools/test_all.py runner discovery."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TEST_DIR.parent

sys.path.insert(0, str(TOOLS_DIR))
import test_all  # noqa: E402


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def test_posix_prefers_native_lua_before_windows_exe() -> None:
    assert_equal(
        test_all.lua_runner_candidates("posix"),
        ("lua5.2", "lua52", "lua", "lua52.exe"),
        "posix candidates",
    )


def test_windows_prefers_windows_lua_exe() -> None:
    assert_equal(
        test_all.lua_runner_candidates("nt"),
        ("lua52.exe", "lua5.2", "lua52", "lua"),
        "windows candidates",
    )


def test_find_lua_runner_skips_unusable_candidates() -> None:
    old_which = test_all.shutil.which
    old_is_lua52_runner = test_all.is_lua52_runner
    old_lua_runner_candidates = test_all.lua_runner_candidates
    try:
        test_all.lua_runner_candidates = lambda: ("lua52.exe", "lua5.2")
        test_all.shutil.which = lambda candidate: f"/fake/{candidate}"
        test_all.is_lua52_runner = lambda command: command == "/fake/lua5.2"

        assert_equal(test_all.find_lua_runner(None), "/fake/lua5.2", "lua runner")
    finally:
        test_all.shutil.which = old_which
        test_all.is_lua52_runner = old_is_lua52_runner
        test_all.lua_runner_candidates = old_lua_runner_candidates


def test_discover_lua_tests_runs_lib_modules_and_tools_lua_tests() -> None:
    old_root_dir = test_all.ROOT_DIR
    old_tools_dir = test_all.TOOLS_DIR

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tools_dir = root / "ModpackTools"
        module_dir = root / "Submodules" / "adamantRunDirector-GodPool"
        lib_tests_dir = root / "adamant-ModpackLib" / "tests"
        module_tests_dir = module_dir / "tests"
        tools_tests_dir = tools_dir / "tests"

        lib_tests_dir.mkdir(parents=True)
        module_tests_dir.mkdir(parents=True)
        tools_tests_dir.mkdir(parents=True)
        (lib_tests_dir / "all.lua").write_text("", encoding="utf-8")
        (module_tests_dir / "all.lua").write_text("", encoding="utf-8")
        (tools_tests_dir / "test_tool_contract.lua").write_text("", encoding="utf-8")

        try:
            test_all.ROOT_DIR = root
            test_all.TOOLS_DIR = tools_dir
            commands = test_all.discover_lua_tests("lua5.2")
        finally:
            test_all.ROOT_DIR = old_root_dir
            test_all.TOOLS_DIR = old_tools_dir

    assert_equal(
        [command.name for command in commands],
        [
            "adamant-ModpackLib",
            "adamantRunDirector-GodPool",
            "ModpackTools/test_tool_contract.lua",
        ],
        "lua test commands",
    )
    assert_equal(
        commands[-1].command,
        ["lua5.2", "ModpackTools/tests/test_tool_contract.lua"],
        "tools lua command",
    )


def main() -> int:
    tests = [
        test_posix_prefers_native_lua_before_windows_exe,
        test_windows_prefers_windows_lua_exe,
        test_find_lua_runner_skips_unusable_candidates,
        test_discover_lua_tests_runs_lib_modules_and_tools_lua_tests,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} test_all tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
