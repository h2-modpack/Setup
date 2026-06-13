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
        coordinator_repo="adamantRunDirector-RunDirector_Modpack",
        root=Path("unused"),
    )


def make_config_with_dependency() -> release_all.ReleaseConfig:
    return release_all.ReleaseConfig(
        org="h2pack-rundirector",
        team="adamantRunDirector",
        coordinator_repo="adamantRunDirector-RunDirector_Modpack",
        dependency_org="h2-modpack",
        dependency_repo="adamant-ModpackLib",
        root=Path("unused"),
    )


def build_plan(
    tag: str,
    targets: str | None,
    config: release_all.ReleaseConfig | None = None,
) -> release_all.ReleasePlan:
    return release_all.build_release_plan(config or make_config(), tag, targets, MODULE_REPOS)


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


def test_mass_release_selects_all_modules_and_coordinator() -> None:
    plan = build_plan("1.2.0", "")
    assert_equal(plan.module_repos, MODULE_REPOS, "mass modules")
    assert_true(plan.coordinator_selected, "mass coordinator selected")


def test_mass_release_ignores_deprecated_dependency_config() -> None:
    plan = build_plan("1.2.0", "", make_config_with_dependency())
    assert_equal(plan.module_repos, MODULE_REPOS, "mass modules")
    assert_true(plan.coordinator_selected, "mass coordinator selected")


def test_targeted_release_accepts_module_and_coordinator_aliases() -> None:
    plan = build_plan(
        "1.2.1",
        "BiomeControl, adamantRunDirector-GodPool, BoonBans, Coordinator, Modpack, RunDirector_Modpack",
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
    assert_true(plan.coordinator_selected, "targeted coordinator selected")


def test_targeted_release_rejects_dependency_aliases() -> None:
    exc = assert_raises(
        "Unsupported release target",
        lambda: build_plan("1.2.1", "Lib", make_config_with_dependency()),
    )
    if "Release Lib from its own repository" not in exc.message:
        raise AssertionError(f"unexpected dependency target message: {exc.message}")


def test_targeted_dependency_zero_patch_reports_dependency_boundary() -> None:
    assert_raises(
        "Unsupported release target",
        lambda: build_plan("3.0.0", "Lib", make_config_with_dependency()),
    )


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


def test_parse_workflow_fields_accepts_key_value_pairs() -> None:
    fields = release_all.parse_workflow_fields(
        [
            "lib-version=3.0.0",
            " dependency-pins=adamantRunDirector-GodPool=3.0.0 ",
        ]
    )
    assert_equal(fields, [
        "lib-version=3.0.0",
        "dependency-pins=adamantRunDirector-GodPool=3.0.0",
    ], "workflow fields")


def test_parse_workflow_fields_rejects_missing_value_separator() -> None:
    assert_raises("Invalid workflow field", lambda: release_all.parse_workflow_fields(["lib-version"]))


def test_build_coordinator_dependency_pin_field_uses_selected_module_repos() -> None:
    field = release_all.build_coordinator_dependency_pin_field(
        [
            "adamantRunDirector-BiomeControl",
            "adamantRunDirector-GodPool",
        ],
        "3.0.0",
    )
    assert_equal(
        field,
        "dependency-pins=adamantRunDirector-BiomeControl=3.0.0,adamantRunDirector-GodPool=3.0.0",
        "coordinator dependency pins",
    )


def test_merge_workflow_fields_combines_shared_and_repo_specific_fields() -> None:
    fields = release_all.merge_workflow_fields(
        "adamantRunDirector-BoonBans",
        ["lib-version=3.0.0"],
        {"adamantRunDirector-BoonBans": ["include-private-padding=true"]},
    )
    assert_equal(fields, [
        "lib-version=3.0.0",
        "include-private-padding=true",
    ], "merged workflow fields")


def test_has_workflow_field_matches_field_name() -> None:
    assert_true(
        release_all.has_workflow_field(["lib-version=3.0.0"], "lib-version"),
        "has lib-version field",
    )
    assert_equal(
        release_all.has_workflow_field(["dependency-pins=Package=3.0.0"], "lib-version"),
        False,
        "missing lib-version field",
    )


def test_release_repos_lists_modules_then_coordinator() -> None:
    config = make_config()
    plan = release_all.ReleasePlan(
        module_repos=[
            "adamantRunDirector-BiomeControl",
            "adamantRunDirector-GodPool",
        ],
        coordinator_selected=True,
    )
    assert_equal(
        release_all.release_repos(config, plan),
        [
            "adamantRunDirector-BiomeControl",
            "adamantRunDirector-GodPool",
            "adamantRunDirector-RunDirector_Modpack",
        ],
        "release repos",
    )


def test_verify_release_plan_ci_checks_selected_repos_and_skips_existing() -> None:
    config = make_config()
    plan = release_all.ReleasePlan(
        module_repos=[
            "adamantRunDirector-BiomeControl",
            "adamantRunDirector-BoonBans",
        ],
        coordinator_selected=True,
    )
    calls: list[tuple[str, str]] = []
    shas = {
        "adamantRunDirector-BiomeControl": "a" * 40,
        "adamantRunDirector-RunDirector_Modpack": "b" * 40,
    }
    old_release_exists = release_all.release_exists
    old_local_repo_head = release_all.local_repo_head
    old_remote_branch_head = release_all.remote_branch_head
    old_successful_ci_run_for_commit = release_all.successful_ci_run_for_commit

    def fake_release_exists(_config, repo, _tag):
        calls.append(("exists", repo))
        return repo == "adamantRunDirector-BoonBans"

    def fake_local_repo_head(_config, repo):
        calls.append(("local", repo))
        return shas[repo]

    def fake_remote_branch_head(_config, repo):
        calls.append(("remote", repo))
        return shas[repo]

    def fake_successful_ci_run_for_commit(_config, repo, sha):
        calls.append(("ci", repo))
        return 1000 + len(sha)

    try:
        release_all.release_exists = fake_release_exists
        release_all.local_repo_head = fake_local_repo_head
        release_all.remote_branch_head = fake_remote_branch_head
        release_all.successful_ci_run_for_commit = fake_successful_ci_run_for_commit

        release_all.verify_release_plan_ci(config, plan, "1.2.0", False)
        assert_equal(calls, [
            ("exists", "adamantRunDirector-BiomeControl"),
            ("local", "adamantRunDirector-BiomeControl"),
            ("remote", "adamantRunDirector-BiomeControl"),
            ("ci", "adamantRunDirector-BiomeControl"),
            ("exists", "adamantRunDirector-BoonBans"),
            ("exists", "adamantRunDirector-RunDirector_Modpack"),
            ("local", "adamantRunDirector-RunDirector_Modpack"),
            ("remote", "adamantRunDirector-RunDirector_Modpack"),
            ("ci", "adamantRunDirector-RunDirector_Modpack"),
        ], "ci preflight calls")
    finally:
        release_all.release_exists = old_release_exists
        release_all.local_repo_head = old_local_repo_head
        release_all.remote_branch_head = old_remote_branch_head
        release_all.successful_ci_run_for_commit = old_successful_ci_run_for_commit


def test_verify_repo_ci_rejects_release_ref_mismatch() -> None:
    config = make_config()
    old_release_exists = release_all.release_exists
    old_local_repo_head = release_all.local_repo_head
    old_remote_branch_head = release_all.remote_branch_head

    try:
        release_all.release_exists = lambda _config, _repo, _tag: False
        release_all.local_repo_head = lambda _config, _repo: "a" * 40
        release_all.remote_branch_head = lambda _config, _repo: "b" * 40

        assert_raises(
            "Release ref mismatch",
            lambda: release_all.verify_repo_ci(
                config,
                "adamantRunDirector-BiomeControl",
                "1.2.0",
                False,
            ),
        )
    finally:
        release_all.release_exists = old_release_exists
        release_all.local_repo_head = old_local_repo_head
        release_all.remote_branch_head = old_remote_branch_head


def test_verify_repo_ci_rejects_missing_successful_ci() -> None:
    config = make_config()
    old_release_exists = release_all.release_exists
    old_local_repo_head = release_all.local_repo_head
    old_remote_branch_head = release_all.remote_branch_head
    old_successful_ci_run_for_commit = release_all.successful_ci_run_for_commit

    try:
        release_all.release_exists = lambda _config, _repo, _tag: False
        release_all.local_repo_head = lambda _config, _repo: "a" * 40
        release_all.remote_branch_head = lambda _config, _repo: "a" * 40
        release_all.successful_ci_run_for_commit = lambda _config, _repo, _sha: None

        assert_raises(
            "CI has not passed",
            lambda: release_all.verify_repo_ci(
                config,
                "adamantRunDirector-BiomeControl",
                "1.2.0",
                False,
            ),
        )
    finally:
        release_all.release_exists = old_release_exists
        release_all.local_repo_head = old_local_repo_head
        release_all.remote_branch_head = old_remote_branch_head
        release_all.successful_ci_run_for_commit = old_successful_ci_run_for_commit


def test_dispatch_repo_uses_configured_branch_ref() -> None:
    config = make_config()
    calls: list[list[str]] = []
    old_list_release_runs = release_all.list_release_runs
    old_run_gh = release_all.run_gh
    old_find_new_release_run = release_all.find_new_release_run

    def fake_run_gh(args, capture_json=False):
        calls.append(args)
        return [] if capture_json else None

    try:
        release_all.list_release_runs = lambda _config, _repo: []
        release_all.run_gh = fake_run_gh
        release_all.find_new_release_run = lambda *_args: 321

        run_id = release_all.dispatch_repo(
            config,
            "adamantRunDirector-BiomeControl",
            "1.2.0",
            True,
        )
        assert_equal(run_id, 321, "dispatch run id")
        assert_equal(calls[0], [
            "workflow",
            "run",
            "release.yaml",
            "--repo",
            "h2pack-rundirector/adamantRunDirector-BiomeControl",
            "--ref",
            "main",
            "--field",
            "tag=1.2.0",
            "--field",
            "is-dry-run=true",
        ], "workflow dispatch command")
    finally:
        release_all.list_release_runs = old_list_release_runs
        release_all.run_gh = old_run_gh
        release_all.find_new_release_run = old_find_new_release_run


def test_dispatch_plan_releases_modules_and_coordinator_only() -> None:
    config = make_config_with_dependency()
    plan = build_plan("1.2.0", "", config)
    calls: list[tuple[str, str, tuple[str, ...]]] = []
    old_release_exists = release_all.release_exists
    old_dispatch_repo = release_all.dispatch_repo
    old_watch_repo = release_all.watch_repo

    def fake_release_exists(_config, _repo, _tag):
        return False

    def fake_dispatch_repo(_config, repo, _tag, _child_dry_run, _repo_fields, shared_fields):
        calls.append((_config.org, repo, tuple(shared_fields or [])))
        return len(calls)

    def fake_watch_repo(_config, _repo, _run_id):
        return None

    try:
        release_all.release_exists = fake_release_exists
        release_all.dispatch_repo = fake_dispatch_repo
        release_all.watch_repo = fake_watch_repo

        module_fields = []
        coordinator_fields = []
        module_fields.append("lib-version=3.0.0")
        coordinator_fields.append("lib-version=3.0.0")
        release_all.dispatch_release_plan(
            config,
            plan,
            "1.2.0",
            True,
            module_fields=module_fields,
            coordinator_fields=coordinator_fields,
        )
        assert_equal(calls[0], ("h2pack-rundirector", MODULE_REPOS[0], ("lib-version=3.0.0",)), "first module dispatch")
        assert_equal(calls[-1], (
            "h2pack-rundirector",
            "adamantRunDirector-RunDirector_Modpack",
            ("lib-version=3.0.0",),
        ), "coordinator dispatch")
    finally:
        release_all.release_exists = old_release_exists
        release_all.dispatch_repo = old_dispatch_repo
        release_all.watch_repo = old_watch_repo


def test_release_phase_waits_for_each_repo_before_dispatching_next() -> None:
    config = make_config()
    calls: list[tuple[str, str]] = []
    old_release_exists = release_all.release_exists
    old_dispatch_repo = release_all.dispatch_repo
    old_watch_repo = release_all.watch_repo

    def fake_release_exists(_config, repo, _tag):
        calls.append(("exists", repo))
        return False

    def fake_dispatch_repo(_config, repo, _tag, _child_dry_run, _repo_fields, _shared_fields):
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

    def fake_dispatch_repo(_config, repo, _tag, _child_dry_run, _repo_fields, _shared_fields):
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
        test_mass_release_selects_all_modules_and_coordinator,
        test_mass_release_ignores_deprecated_dependency_config,
        test_targeted_release_accepts_module_and_coordinator_aliases,
        test_targeted_release_rejects_dependency_aliases,
        test_targeted_dependency_zero_patch_reports_dependency_boundary,
        test_targeted_release_deduplicates_modules,
        test_old_prefixed_module_target_is_rejected,
        test_unknown_target_reports_current_repo_name,
        test_mass_release_requires_zero_patch,
        test_targeted_release_requires_nonzero_patch,
        test_empty_target_list_is_rejected,
        test_dispatch_fields_include_generic_repo_fields,
        test_parse_repo_fields_groups_fields_by_repo,
        test_parse_workflow_fields_accepts_key_value_pairs,
        test_parse_workflow_fields_rejects_missing_value_separator,
        test_build_coordinator_dependency_pin_field_uses_selected_module_repos,
        test_merge_workflow_fields_combines_shared_and_repo_specific_fields,
        test_has_workflow_field_matches_field_name,
        test_release_repos_lists_modules_then_coordinator,
        test_verify_release_plan_ci_checks_selected_repos_and_skips_existing,
        test_verify_repo_ci_rejects_release_ref_mismatch,
        test_verify_repo_ci_rejects_missing_successful_ci,
        test_dispatch_repo_uses_configured_branch_ref,
        test_dispatch_plan_releases_modules_and_coordinator_only,
        test_release_phase_waits_for_each_repo_before_dispatching_next,
        test_release_phase_skips_existing_releases,
    ]

    for test in tests:
        test()
    print(f"{len(tests)} release_all dry-run tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
