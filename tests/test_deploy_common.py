#!/usr/bin/env python3
"""Tests for ModpackTools/local_deploy/steps/common.py."""

from __future__ import annotations

import os
import platform
import sys
import tempfile
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TEST_DIR.parent

sys.path.insert(0, str(TOOLS_DIR / "local_deploy"))
from steps import common  # noqa: E402


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def assert_raises(message: str, func) -> Exception:
    try:
        func()
    except Exception as exc:
        if message not in str(exc):
            raise AssertionError(f"expected {message!r} in {exc!r}") from exc
        return exc
    raise AssertionError(f"expected exception containing {message!r}")


def test_get_toml_info_reads_package_table() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        toml_path = Path(tmp) / "thunderstore.toml"
        toml_path.write_text(
            """
[package]
# comments and spacing should not matter.
namespace = "adamant"
name = "RunDirector_Test"
""".strip(),
            encoding="utf-8",
        )

        namespace, name = common.get_toml_info(toml_path)

    assert_equal(namespace, "adamant", "namespace")
    assert_equal(name, "RunDirector_Test", "name")


def test_get_toml_info_requires_name() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        toml_path = Path(tmp) / "thunderstore.toml"
        toml_path.write_text('[package]\nnamespace = "adamant"\n', encoding="utf-8")

        assert_raises("missing package.name", lambda: common.get_toml_info(toml_path))


def test_windows_profile_path_requires_appdata() -> None:
    if platform.system() != "Windows":
        return

    old_appdata = os.environ.pop("APPDATA", None)
    try:
        assert_raises("APPDATA is not set", lambda: common.get_profile_path("h2-dev"))
    finally:
        if old_appdata is not None:
            os.environ["APPDATA"] = old_appdata


def main() -> int:
    tests = [
        test_get_toml_info_reads_package_table,
        test_get_toml_info_requires_name,
        test_windows_profile_path_requires_appdata,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} deploy common tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
