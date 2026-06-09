#!/usr/bin/env python3
"""Dry-run tests for ModpackTools/github/release_all.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TEST_DIR.parent

sys.path.insert(0, str(TOOLS_DIR / "github"))
import release_all  # noqa: E402


MODULE_REPOS = [
    "adamantRunDirector-BiomeControl",
    "adamantRunDirector-BoonBans",
    "adamantRunDirector-GodPool",
]


def make_config() -> release_all.ReleaseConfig:
    return release_all.ReleaseConfig(
        org="h2pack-rundirector",
        team="adamantRunDirector",
        core_repo="adamantRunDirector-RunDirector_Modpack",
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
        "BiomeControl, adamantRunDirector-GodPool, BoonBans, Core, Modpack, RunDirector_Modpack",
    )
    assert_equal(
        plan.module_repos,
        [
            "adamantRunDirector-BiomeControl",
            "adamantRunDirector-GodPool",
            "adamantRunDirector-BoonBans",
        ],
        "targeted modules",
    )
    assert_true(plan.core_selected, "targeted core selected")


def test_targeted_release_deduplicates_modules() -> None:
    plan = build_plan(
        "1.2.1",
        "BiomeControl, adamantRunDirector-BiomeControl",
    )
    assert_equal(plan.module_repos, ["adamantRunDirector-BiomeControl"], "deduped modules")


def test_old_prefixed_module_target_is_rejected() -> None:
    exc = assert_raises(
        "Unknown release target",
        lambda: build_plan("1.2.1", "RunDirector_GodPool"),
    )
    if "adamantRunDirector-RunDirector_GodPool" not in exc.message:
        raise AssertionError(f"unexpected unknown target message: {exc.message}")


def test_unknown_target_reports_current_repo_name() -> None:
    exc = assert_raises(
        "Unknown release target",
        lambda: build_plan("1.2.1", "MissingThing"),
    )
    if "adamantRunDirector-MissingThing" not in exc.message:
        raise AssertionError(f"unexpected unknown target message: {exc.message}")


def test_mass_release_requires_zero_patch() -> None:
    assert_raises("Invalid Mass Release Version", lambda: build_plan("1.2.1", ""))


def test_targeted_release_requires_nonzero_patch() -> None:
    assert_raises("Invalid Hotfix Version", lambda: build_plan("1.2.0", "BiomeControl"))


def test_empty_target_list_is_rejected() -> None:
    assert_raises("No release targets", lambda: build_plan("1.2.1", " , , "))


def test_dispatch_fields_include_generic_repo_fields() -> None:
    fields = release_all.build_dispatch_fields(
        "1.2.1",
        True,
        ["include-private-padding=true"],
    )
    assert_equal(fields, [
        "tag=1.2.1",
        "is-dry-run=true",
        "include-private-padding=true",
    ], "dispatch fields")


def test_parse_repo_fields_groups_fields_by_repo() -> None:
    fields = release_all.parse_repo_fields(
        [
            "adamantRunDirector-BoonBans:include-private-padding=true",
            "adamantRunDirector-GodPool:custom=value",
        ]
    )
    assert_equal(fields, {
        "adamantRunDirector-BoonBans": ["include-private-padding=true"],
        "adamantRunDirector-GodPool": ["custom=value"],
    }, "repo fields")


def test_release_phase_waits_for_each_repo_before_dispatching_next() -> None:
    config = make_config()
    calls: list[tuple[str, str]] = []
    old_release_exists = release_all.release_exists
    old_dispatch_repo = release_all.dispatch_repo
    old_watch_repo = release_all.watch_repo

    def fake_release_exists(_config, repo, _tag):
        calls.append(("exists", repo))
        return False

    def fake_dispatch_repo(_config, repo, _tag, _child_dry_run, _repo_fields):
        calls.append(("dispatch", repo))
        return 100 + len(calls)

    def fake_watch_repo(_config, repo, _run_id):
        calls.append(("watch", repo))
        if repo == "adamantRunDirector-BoonBans":
            raise subprocess.CalledProcessError(1, ["gh", "run", "watch"])

    try:
        release_all.release_exists = fake_release_exists
        release_all.dispatch_repo = fake_dispatch_repo
        release_all.watch_repo = fake_watch_repo

        exc = assert_raises(
            "Release failed",
            lambda: release_all.release_phase(
                config,
                "Module releases",
                MODULE_REPOS,
                "1.2.0",
                False,
            ),
        )
        if "Completed 1 / 3" not in exc.message:
            raise AssertionError(f"unexpected failure message: {exc.message}")
        assert_equal(calls, [
            ("exists", "adamantRunDirector-BiomeControl"),
            ("dispatch", "adamantRunDirector-BiomeControl"),
            ("watch", "adamantRunDirector-BiomeControl"),
            ("exists", "adamantRunDirector-BoonBans"),
            ("dispatch", "adamantRunDirector-BoonBans"),
            ("watch", "adamantRunDirector-BoonBans"),
        ], "sequential release calls")
    finally:
        release_all.release_exists = old_release_exists
        release_all.dispatch_repo = old_dispatch_repo
        release_all.watch_repo = old_watch_repo


def test_release_phase_skips_existing_releases() -> None:
    config = make_config()
    calls: list[tuple[str, str]] = []
    old_release_exists = release_all.release_exists
    old_dispatch_repo = release_all.dispatch_repo
    old_watch_repo = release_all.watch_repo

    def fake_release_exists(_config, repo, _tag):
        calls.append(("exists", repo))
        return repo == "adamantRunDirector-BoonBans"

    def fake_dispatch_repo(_config, repo, _tag, _child_dry_run, _repo_fields):
        calls.append(("dispatch", repo))
        return 200 + len(calls)

    def fake_watch_repo(_config, repo, _run_id):
        calls.append(("watch", repo))

    try:
        release_all.release_exists = fake_release_exists
        release_all.dispatch_repo = fake_dispatch_repo
        release_all.watch_repo = fake_watch_repo

        succeeded = release_all.release_phase(
            config,
            "Module releases",
            MODULE_REPOS,
            "1.2.0",
            False,
        )
        assert_equal(succeeded, 3, "release success count")
        assert_equal(calls, [
            ("exists", "adamantRunDirector-BiomeControl"),
            ("dispatch", "adamantRunDirector-BiomeControl"),
            ("watch", "adamantRunDirector-BiomeControl"),
            ("exists", "adamantRunDirector-BoonBans"),
            ("exists", "adamantRunDirector-GodPool"),
            ("dispatch", "adamantRunDirector-GodPool"),
            ("watch", "adamantRunDirector-GodPool"),
        ], "skip existing release calls")
    finally:
        release_all.release_exists = old_release_exists
        release_all.dispatch_repo = old_dispatch_repo
        release_all.watch_repo = old_watch_repo


def main() -> int:
    tests = [
        test_mass_release_selects_all_modules_and_core,
        test_targeted_release_accepts_module_and_core_aliases,
        test_targeted_release_deduplicates_modules,
        test_old_prefixed_module_target_is_rejected,
        test_unknown_target_reports_current_repo_name,
        test_mass_release_requires_zero_patch,
        test_targeted_release_requires_nonzero_patch,
        test_empty_target_list_is_rejected,
        test_dispatch_fields_include_generic_repo_fields,
        test_parse_repo_fields_groups_fields_by_repo,
        test_release_phase_waits_for_each_repo_before_dispatching_next,
        test_release_phase_skips_existing_releases,
    ]

    for test in tests:
        test()
    print(f"{len(tests)} release_all dry-run tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
