#!/usr/bin/env python3
"""Coordinate pack-wide release workflow dispatches.

This script is intentionally pack-parameterized so shell workflow YAML only
passes pack identity while the release planning and dispatch behavior remains
testable in Setup.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


GITHUB_DIR = Path(__file__).resolve().parent
SETUP_DIR = GITHUB_DIR.parent
ROOT_DIR = SETUP_DIR.parent
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class ReleaseError(Exception):
    def __init__(self, title: str, message: str):
        super().__init__(message)
        self.title = title
        self.message = message


@dataclass(frozen=True)
class ReleaseConfig:
    org: str
    namespace: str
    pack_pascal: str
    core_repo: str
    root: Path = ROOT_DIR
    workflow: str = "release.yaml"
    branch: str = "main"
    poll_attempts: int = 30
    poll_interval: int = 5

    @property
    def module_prefix(self) -> str:
        return f"{self.namespace}-{self.pack_pascal}_"


@dataclass(frozen=True)
class ReleasePlan:
    module_repos: list[str]
    core_selected: bool

    def total(self) -> int:
        return len(self.module_repos) + (1 if self.core_selected else 0)


def parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def validate_tag(tag: str, targeted: bool) -> None:
    if not VERSION_PATTERN.match(tag or ""):
        raise ReleaseError(
            "Invalid package version number",
            "Version numbers must follow the Major.Minor.Patch format (e.g. 1.45.320).",
        )

    patch = tag.split(".")[2]
    if targeted:
        if patch == "0":
            raise ReleaseError(
                "Invalid Hotfix Version",
                "Targeted hotfixes must use a patch version greater than .0 (e.g. 1.2.1).",
            )
    elif patch != "0":
        raise ReleaseError(
            "Invalid Mass Release Version",
            "Mass releases (all modules) must end in .0 (e.g., 1.2.0) to reserve patch numbers for hotfixes.",
        )


def discover_module_repos(config: ReleaseConfig) -> list[str]:
    submodules = config.root / "Submodules"
    if not submodules.is_dir():
        return []

    repos: list[str] = []
    for entry in sorted(submodules.iterdir(), key=lambda path: path.name.lower()):
        if not entry.is_dir():
            continue
        if not entry.name.startswith(config.module_prefix):
            continue
        if not (entry / "thunderstore.toml").is_file() and not (entry / "src").is_dir():
            continue
        repos.append(entry.name)
    return repos


def _casefold_map(values: list[str]) -> dict[str, str]:
    return {value.casefold(): value for value in values}


def core_aliases(config: ReleaseConfig) -> set[str]:
    aliases = {
        "Core",
        config.core_repo,
        f"{config.pack_pascal}_Core",
        f"Modpack{config.pack_pascal}Core",
    }

    namespace_prefix = f"{config.namespace}-"
    if config.core_repo.startswith(namespace_prefix):
        aliases.add(config.core_repo[len(namespace_prefix):])

    return aliases


def module_aliases(config: ReleaseConfig, repo: str) -> set[str]:
    aliases = {repo}
    namespace_prefix = f"{config.namespace}-"
    if repo.startswith(namespace_prefix):
        aliases.add(repo[len(namespace_prefix):])
    if repo.startswith(config.module_prefix):
        aliases.add(repo[len(config.module_prefix):])
    return aliases


def normalize_release_target(
    raw: str,
    config: ReleaseConfig,
    available_module_repos: list[str],
) -> tuple[str, str] | None:
    target = (raw or "").strip()
    if not target:
        return None

    if target.casefold() in {alias.casefold() for alias in core_aliases(config)}:
        return ("core", config.core_repo)

    alias_to_repo: dict[str, str] = {}
    for repo in available_module_repos:
        for alias in module_aliases(config, repo):
            alias_to_repo[alias.casefold()] = repo

    direct = alias_to_repo.get(target.casefold())
    if direct:
        return ("module", direct)

    candidates = [target]
    if target.startswith(config.namespace + "-"):
        candidates.append(target)
    elif target.startswith(config.pack_pascal + "_"):
        candidates.append(f"{config.namespace}-{target}")
    else:
        candidates.append(f"{config.module_prefix}{target}")

    repo_map = _casefold_map(available_module_repos)
    for candidate in candidates:
        repo = repo_map.get(candidate.casefold())
        if repo:
            return ("module", repo)

    normalized = candidates[-1]
    raise ReleaseError(
        "Unknown release target",
        f"{normalized} is not a checked-out module repo.",
    )


def build_release_plan(
    config: ReleaseConfig,
    tag: str,
    targets: str | None,
    available_module_repos: list[str] | None = None,
) -> ReleasePlan:
    requested_filter = (targets or "").strip()
    targeted = bool(requested_filter)
    validate_tag(tag, targeted)

    available_modules = (
        discover_module_repos(config)
        if available_module_repos is None
        else list(available_module_repos)
    )
    module_repos: list[str] = []
    seen_modules: set[str] = set()
    core_selected = False

    if not targeted:
        return ReleasePlan(module_repos=available_modules, core_selected=True)

    for requested in requested_filter.split(","):
        normalized = normalize_release_target(requested, config, available_modules)
        if not normalized:
            continue

        kind, repo = normalized
        if kind == "core":
            core_selected = True
        elif repo not in seen_modules:
            seen_modules.add(repo)
            module_repos.append(repo)

    plan = ReleasePlan(module_repos=module_repos, core_selected=core_selected)
    if plan.total() == 0:
        raise ReleaseError(
            "No release targets",
            "No module or core release targets were selected.",
        )
    return plan


def print_plan(plan: ReleasePlan, config: ReleaseConfig) -> None:
    print("Release order:")
    for repo in plan.module_repos:
        print(f"  - {repo}")
    if plan.core_selected:
        print(f"  - {config.core_repo}")


def run_gh(args: list[str], capture_json: bool = False) -> object | None:
    result = subprocess.run(
        ["gh", *args],
        check=True,
        capture_output=capture_json,
        text=True,
    )
    if not capture_json:
        return None
    output = result.stdout.strip()
    if not output:
        return None
    return json.loads(output)


def list_release_runs(config: ReleaseConfig, repo: str) -> list[dict]:
    data = run_gh(
        [
            "run",
            "list",
            "--repo",
            f"{config.org}/{repo}",
            "--workflow",
            config.workflow,
            "--branch",
            config.branch,
            "--limit",
            "50",
            "--json",
            "databaseId,createdAt,event,displayTitle",
        ],
        capture_json=True,
    )
    return data if isinstance(data, list) else []


def release_run_title(tag: str, child_dry_run: bool) -> str:
    return f"{'Dry-run' if child_dry_run else 'Release'} {tag}"


def find_new_release_run(
    config: ReleaseConfig,
    repo: str,
    baseline_ids: set[int],
    earliest_created_at: datetime,
    expected_title: str,
) -> int | None:
    runs = list_release_runs(config, repo)
    candidates = []
    for run in runs:
        database_id = run.get("databaseId")
        if database_id in baseline_ids:
            continue
        if run.get("event") != "workflow_dispatch":
            continue
        if run.get("displayTitle") != expected_title:
            continue

        created_at_raw = run.get("createdAt")
        if created_at_raw:
            created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
            if created_at < earliest_created_at:
                continue

        candidates.append(run)

    if not candidates:
        return None

    candidates.sort(key=lambda item: item.get("createdAt") or "", reverse=True)
    return int(candidates[0]["databaseId"])


def dispatch_repo(config: ReleaseConfig, repo: str, tag: str, child_dry_run: bool) -> int:
    print(f"--- Triggering: {config.org}/{repo} ---")
    baseline_ids = {
        int(run["databaseId"])
        for run in list_release_runs(config, repo)
        if run.get("databaseId") is not None
    }
    dispatched_after = datetime.now(timezone.utc)

    run_gh(
        [
            "workflow",
            "run",
            config.workflow,
            "--repo",
            f"{config.org}/{repo}",
            "--field",
            f"tag={tag}",
            "--field",
            f"is-dry-run={'true' if child_dry_run else 'false'}",
        ]
    )

    expected_title = release_run_title(tag, child_dry_run)
    for _ in range(config.poll_attempts):
        run_id = find_new_release_run(config, repo, baseline_ids, dispatched_after, expected_title)
        if run_id is not None:
            print(f"  Dispatched as run {run_id}.")
            return run_id
        time.sleep(config.poll_interval)

    raise ReleaseError(
        "Release dispatch failed",
        f"Failed to find dispatched workflow run for {config.org}/{repo}.",
    )


def watch_repo(config: ReleaseConfig, repo: str, run_id: int) -> None:
    print(f"--- Waiting: {config.org}/{repo} run {run_id} ---")
    run_gh(
        [
            "run",
            "watch",
            str(run_id),
            "--repo",
            f"{config.org}/{repo}",
            "--exit-status",
            "--interval",
            "10",
        ]
    )


def release_phase(
    config: ReleaseConfig,
    title: str,
    repos: list[str],
    tag: str,
    child_dry_run: bool,
) -> int:
    if not repos:
        return 0

    print("")
    print("==========================================")
    print(f"  {title}")
    print("==========================================")

    dispatched: list[tuple[str, int]] = []
    dispatch_failed = 0
    for repo in repos:
        try:
            dispatched.append((repo, dispatch_repo(config, repo, tag, child_dry_run)))
        except (ReleaseError, subprocess.CalledProcessError) as exc:
            dispatch_failed += 1
            print(f"  FAILED to dispatch {config.org}/{repo}: {exc}")

    if dispatch_failed > 0:
        raise ReleaseError(
            "Release dispatch failed",
            f"{dispatch_failed} child workflow dispatch(es) failed during {title}.",
        )

    succeeded = 0
    release_failed = 0
    for repo, run_id in dispatched:
        try:
            watch_repo(config, repo, run_id)
            succeeded += 1
        except subprocess.CalledProcessError:
            release_failed += 1

    if release_failed > 0:
        raise ReleaseError(
            "Release failed",
            f"{release_failed} child workflow run(s) failed during {title}.",
        )

    return succeeded


def dispatch_release_plan(
    config: ReleaseConfig,
    plan: ReleasePlan,
    tag: str,
    child_dry_run: bool,
) -> None:
    succeeded = release_phase(config, "Module releases", plan.module_repos, tag, child_dry_run)
    if plan.core_selected:
        succeeded += release_phase(config, "Core release", [config.core_repo], tag, child_dry_run)

    print("")
    print("==========================================")
    print(f"  Completed: {succeeded} / {plan.total()}")
    print("==========================================")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coordinate pack-wide release dispatches.")
    parser.add_argument("--org", required=True, help="GitHub org that owns the pack repos.")
    parser.add_argument("--namespace", required=True, help="Thunderstore namespace / repo prefix.")
    parser.add_argument("--pack-pascal", required=True, help="Pack id in PascalCase, e.g. RunDirector.")
    parser.add_argument("--core-repo", required=True, help="Coordinator/core repo name.")
    parser.add_argument("--tag", required=True, help="Release version tag.")
    parser.add_argument("--targets", nargs="?", default="", const="", help="Comma-separated release targets. Blank means all.")
    parser.add_argument("--child-dry-run", default="false", help="Pass dry-run mode to child release workflows.")
    parser.add_argument("--plan-only", action="store_true", help="Validate and print the plan without dispatching.")
    parser.add_argument("--root", default=str(ROOT_DIR), help="Shell repo root. Defaults to parent of Setup/.")
    parser.add_argument("--workflow", default="release.yaml", help="Child workflow filename.")
    parser.add_argument("--branch", default="main", help="Child workflow branch.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = ReleaseConfig(
        org=args.org,
        namespace=args.namespace,
        pack_pascal=args.pack_pascal,
        core_repo=args.core_repo,
        root=Path(args.root).resolve(),
        workflow=args.workflow,
        branch=args.branch,
    )
    child_dry_run = parse_bool(args.child_dry_run)

    try:
        plan = build_release_plan(config, args.tag, args.targets)
        print_plan(plan, config)
        if not args.plan_only:
            dispatch_release_plan(config, plan, args.tag, child_dry_run)
        return 0
    except ReleaseError as exc:
        print(f"::error title={exc.title}::{exc.message}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"::error title=GitHub CLI failed::gh exited with {exc.returncode}", file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
