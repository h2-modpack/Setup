#!/usr/bin/env python3
"""Tests for local_deploy/steps/links.py."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
DEPLOY_DIR = TOOLS_DIR / "local_deploy"
if str(DEPLOY_DIR) not in sys.path:
    sys.path.insert(0, str(DEPLOY_DIR))

from steps import links  # noqa: E402


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def test_auto_mode_uses_copy_for_wsl_windows_profile() -> None:
    old_is_wsl = links.is_wsl
    try:
        links.is_wsl = lambda: True
        mode = links.resolve_link_mode("auto", "/mnt/c/Users/Example/AppData/Roaming/r2modmanPlus-local")
    finally:
        links.is_wsl = old_is_wsl

    assert_equal(mode, "copy", "resolved mode")


def test_auto_mode_uses_symlink_for_same_side_profile() -> None:
    old_is_wsl = links.is_wsl
    try:
        links.is_wsl = lambda: True
        mode = links.resolve_link_mode("auto", "/home/example/.config/r2modmanPlus-local")
    finally:
        links.is_wsl = old_is_wsl

    assert_equal(mode, "symlink", "resolved mode")


def test_auto_mode_uses_copy_for_windows_python_wsl_unc_source() -> None:
    old_is_wsl = links.is_wsl
    old_platform_system = links.platform.system
    try:
        links.is_wsl = lambda: False
        links.platform.system = lambda: "Windows"
        mode = links.resolve_link_mode(
            "auto",
            r"C:\Users\Example\AppData\Roaming\r2modmanPlus-local\HadesII\profiles\h2-dev\ReturnOfModding",
            r"\\wsl.localhost\Ubuntu\home\example\run-director-modpack",
        )
    finally:
        links.is_wsl = old_is_wsl
        links.platform.system = old_platform_system

    assert_equal(mode, "copy", "resolved mode")


def test_copy_tree_overwrites_existing_directory() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "source"
        target = root / "profile" / "plugins" / "Package"

        source.mkdir()
        (source / "manifest.json").write_text('{"new": true}\n', encoding="utf-8")
        target.mkdir(parents=True)
        (target / "stale.txt").write_text("old\n", encoding="utf-8")

        copied = links.copy_tree(str(source), str(target), overwrite=True)

        if not copied:
            raise AssertionError("expected copy_tree to copy")
        assert_equal((target / "manifest.json").read_text(encoding="utf-8"), '{"new": true}\n', "copied manifest")
        if (target / "stale.txt").exists():
            raise AssertionError("expected stale file to be removed")


def main() -> int:
    tests = [
        test_auto_mode_uses_copy_for_wsl_windows_profile,
        test_auto_mode_uses_symlink_for_same_side_profile,
        test_auto_mode_uses_copy_for_windows_python_wsl_unc_source,
        test_copy_tree_overwrites_existing_directory,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} deploy links tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
