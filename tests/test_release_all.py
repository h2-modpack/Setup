#!/usr/bin/env python3
"""Dry-run tests for Setup/github/release_all.py."""

from __future__ import annotations

import sys
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
SETUP_DIR = TEST_DIR.parent

sys.path.insert(0, str(SETUP_DIR / "github"))
import release_all  # noqa: E402


MODULE_REPOS = [
    "adamant-RunDirector_BiomeControl",
    "adamant-RunDirector_BoonBans",
    "adamant-RunDirector_GodPool",
]


def make_config() -> release_all.ReleaseConfig:
    return release_all.ReleaseConfig(
        org="h2pack-rundirector",
        namespace="adamant",
        pack_pascal="RunDirector",
        core_repo="adamant-RunDirector_Core",
        root=Path("unused"),
    )


def build_plan(tag: str, targets: str | None) -> release_all.ReleasePlan:
    return release_all.build_release_plan(make_config(), tag, targets, MODULE_REPOS)


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def assert_true(value, label: str) -> None:
    if not value:
        raise AssertionError(f"{label}: expected truthy value")


def assert_raises(title: str, func) -> release_all.ReleaseError:
    try:
        func()
    except release_all.ReleaseError as exc:
        assert_equal(exc.title, title, "error title")
        return exc
    raise AssertionError(f"expected ReleaseError titled {title!r}")


def test_mass_release_selects_all_modules_and_core() -> None:
    plan = build_plan("1.2.0", "")
    assert_equal(plan.module_repos, MODULE_REPOS, "mass modules")
    assert_true(plan.core_selected, "mass core selected")


def test_targeted_release_accepts_module_and_core_aliases() -> None:
    plan = build_plan(
        "1.2.1",
        "BiomeControl, RunDirector_GodPool, adamant-RunDirector_BoonBans, Core, ModpackRunDirectorCore",
    )
    assert_equal(
        plan.module_repos,
        [
            "adamant-RunDirector_BiomeControl",
            "adamant-RunDirector_GodPool",
            "adamant-RunDirector_BoonBans",
        ],
        "targeted modules",
    )
    assert_true(plan.core_selected, "targeted core selected")


def test_targeted_release_deduplicates_modules() -> None:
    plan = build_plan(
        "1.2.1",
        "BiomeControl, adamant-RunDirector_BiomeControl, RunDirector_BiomeControl",
    )
    assert_equal(plan.module_repos, ["adamant-RunDirector_BiomeControl"], "deduped modules")


def test_unknown_target_reports_normalized_repo_name() -> None:
    exc = assert_raises(
        "Unknown release target",
        lambda: build_plan("1.2.1", "MissingThing"),
    )
    if "adamant-RunDirector_MissingThing" not in exc.message:
        raise AssertionError(f"unexpected unknown target message: {exc.message}")


def test_mass_release_requires_zero_patch() -> None:
    assert_raises("Invalid Mass Release Version", lambda: build_plan("1.2.1", ""))


def test_targeted_release_requires_nonzero_patch() -> None:
    assert_raises("Invalid Hotfix Version", lambda: build_plan("1.2.0", "BiomeControl"))


def test_empty_target_list_is_rejected() -> None:
    assert_raises("No release targets", lambda: build_plan("1.2.1", " , , "))


def main() -> int:
    tests = [
        test_mass_release_selects_all_modules_and_core,
        test_targeted_release_accepts_module_and_core_aliases,
        test_targeted_release_deduplicates_modules,
        test_unknown_target_reports_normalized_repo_name,
        test_mass_release_requires_zero_patch,
        test_targeted_release_requires_nonzero_patch,
        test_empty_target_list_is_rejected,
    ]

    for test in tests:
        test()
    print(f"{len(tests)} release_all dry-run tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
