#!/usr/bin/env python3
"""Coordinate pack-wide release workflow dispatches.

This script is intentionally pack-parameterized so shell workflow YAML only
passes pack identity while the release planning and dispatch behavior remains
testable in ModpackTools.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path


GITHUB_DIR = Path(__file__).resolve().parent
TOOLS_DIR = GITHUB_DIR.parent
ROOT_DIR = TOOLS_DIR.parent
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class ReleaseError(Exception):
    def __init__(self, title: str, message: str):
        super().__init__(message)
        self.title = title
        self.message = message


@dataclass(frozen=True)
class ReleaseConfig:
    org: str
    team: str
    coordinator_repo: str
    dependency_repo: str | None = None
    dependency_org: str | None = None
    root: Path = ROOT_DIR
    workflow: str = "release.yaml"
    branch: str = "main"
    poll_attempts: int = 30
    poll_interval: int = 5

    @property
    def module_prefix(self) -> str:
        return f"{self.team}-"


@dataclass(frozen=True)
class ReleasePlan:
    dependency_selected: bool
    module_repos: list[str]
    coordinator_selected: bool

    def total(self) -> int:
        return len(self.module_repos) + (1 if self.coordinator_selected else 0) + (1 if self.dependency_selected else 0)


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


def coordinator_aliases(config: ReleaseConfig) -> set[str]:
    aliases = {
        "Coordinator",
        "Modpack",
        config.coordinator_repo,
    }

    team_prefix = f"{config.team}-"
    if config.coordinator_repo.startswith(team_prefix):
        aliases.add(config.coordinator_repo[len(team_prefix):])

    return aliases


def dependency_aliases(config: ReleaseConfig) -> set[str]:
    if not config.dependency_repo:
        return set()

    aliases = {
        "Dependency",
        "Lib",
        "ModpackLib",
        config.dependency_repo,
    }
    if config.dependency_repo.startswith("adamant-"):
        aliases.add(config.dependency_repo[len("adamant-"):])

    return aliases


def module_aliases(config: ReleaseConfig, repo: str) -> set[str]:
    aliases = {repo}
    team_prefix = f"{config.team}-"
    if repo.startswith(team_prefix):
        package_name = repo[len(team_prefix):]
        aliases.add(package_name)
    return aliases


def normalize_release_target(
    raw: str,
    config: ReleaseConfig,
    available_module_repos: list[str],
) -> tuple[str, str] | None:
    target = (raw or "").strip()
    if not target:
        return None

    if target.casefold() in {alias.casefold() for alias in coordinator_aliases(config)}:
        return ("coordinator", config.coordinator_repo)

    if target.casefold() in {alias.casefold() for alias in dependency_aliases(config)}:
        return ("dependency", config.dependency_repo or "")

    alias_to_repo: dict[str, str] = {}
    for repo in available_module_repos:
        for alias in module_aliases(config, repo):
            alias_to_repo[alias.casefold()] = repo

    direct = alias_to_repo.get(target.casefold())
    if direct:
        return ("module", direct)

    candidates = [target]
    if target.startswith(config.team + "-"):
        candidates.append(target)
    else:
        candidates.append(f"{config.module_prefix}{target}")

    repo_map = _casefold_map(available_module_repos)
    for candidate in candidates:
        repo = repo_map.get(candidate.casefold())
        if repo:
            return ("module", repo)

    if target.startswith(config.team + "-"):
        normalized = target
    else:
        normalized = f"{config.module_prefix}{target}"
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
    coordinator_selected = False
    dependency_selected = False

    if not targeted:
        return ReleasePlan(
            dependency_selected=config.dependency_repo is not None,
            module_repos=available_modules,
            coordinator_selected=True,
        )

    for requested in requested_filter.split(","):
        normalized = normalize_release_target(requested, config, available_modules)
        if not normalized:
            continue

        kind, repo = normalized
        if kind == "dependency":
            dependency_selected = True
        elif kind == "coordinator":
            coordinator_selected = True
        elif repo not in seen_modules:
            seen_modules.add(repo)
            module_repos.append(repo)

    plan = ReleasePlan(
        dependency_selected=dependency_selected,
        module_repos=module_repos,
        coordinator_selected=coordinator_selected,
    )
    if plan.total() == 0:
        raise ReleaseError(
            "No release targets",
            "No dependency, module, or coordinator release targets were selected.",
        )
    return plan


def print_plan(plan: ReleasePlan, config: ReleaseConfig) -> None:
    print("Release order:")
    if plan.dependency_selected and config.dependency_repo:
        print(f"  - {config.dependency_repo}")
    for repo in plan.module_repos:
        print(f"  - {repo}")
    if plan.coordinator_selected:
        print(f"  - {config.coordinator_repo}")


def parse_repo_fields(raw_fields: list[str] | None) -> dict[str, list[str]]:
    repo_fields: dict[str, list[str]] = {}
    for raw in raw_fields or []:
        value = (raw or "").strip()
        if not value:
            continue

        repo, separator, field = value.partition(":")
        if not separator or not repo.strip() or not field.strip() or "=" not in field:
            raise ReleaseError(
                "Invalid repo workflow field",
                "Repo workflow fields must use the repo:key=value format.",
            )

        repo_fields.setdefault(repo.strip(), []).append(field.strip())
    return repo_fields


def parse_workflow_fields(raw_fields: list[str] | None) -> list[str]:
    fields: list[str] = []
    for raw in raw_fields or []:
        field = (raw or "").strip()
        if not field:
            continue
        if "=" not in field:
            raise ReleaseError(
                "Invalid workflow field",
                "Workflow fields must use the key=value format.",
            )
        fields.append(field)
    return fields


def build_coordinator_dependency_pin_field(module_repos: list[str], tag: str) -> str | None:
    if not module_repos:
        return None
    pins = ",".join(f"{repo}={tag}" for repo in module_repos)
    return f"dependency-pins={pins}"


def merge_workflow_fields(
    repo: str,
    shared_fields: list[str] | None,
    repo_fields: dict[str, list[str]] | None,
) -> list[str]:
    fields = list(shared_fields or [])
    fields.extend((repo_fields or {}).get(repo, []))
    return fields


def has_workflow_field(fields: list[str], key: str) -> bool:
    return workflow_field_value(fields, key) is not None


def workflow_field_value(fields: list[str], key: str) -> str | None:
    expected = key.strip()
    for field in fields:
        field_key, separator, value = field.partition("=")
        if separator and field_key.strip() == expected:
            return value.strip()
    return None


def enforce_dependency_lib_version(
    fields: list[str],
    tag: str,
    label: str,
) -> None:
    current = workflow_field_value(fields, "lib-version")
    if current is None:
        fields.append(f"lib-version={tag}")
        return
    if current != tag:
        raise ReleaseError(
            "Conflicting Lib dependency version",
            f"{label} lib-version is {current}, but selected dependency release uses tag {tag}.",
        )


def dependency_release_config(config: ReleaseConfig) -> ReleaseConfig:
    return replace(config, org=config.dependency_org or config.org)


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


def release_exists(config: ReleaseConfig, repo: str, tag: str) -> bool:
    result = subprocess.run(
        [
            "gh",
            "release",
            "view",
            tag,
            "--repo",
            f"{config.org}/{repo}",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True

    output = f"{result.stdout}\n{result.stderr}".casefold()
    if "not found" in output or "could not find" in output:
        return False

    raise subprocess.CalledProcessError(
        result.returncode,
        result.args,
        output=result.stdout,
        stderr=result.stderr,
    )


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


def build_dispatch_fields(
    tag: str,
    child_dry_run: bool,
    extra_fields: list[str] | None = None,
) -> list[str]:
    fields = [
        f"tag={tag}",
        f"is-dry-run={'true' if child_dry_run else 'false'}",
    ]
    fields.extend(extra_fields or [])
    return fields


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


def dispatch_repo(
    config: ReleaseConfig,
    repo: str,
    tag: str,
    child_dry_run: bool,
    repo_fields: dict[str, list[str]] | None = None,
    shared_fields: list[str] | None = None,
) -> int:
    print(f"--- Triggering: {config.org}/{repo} ---")
    baseline_ids = {
        int(run["databaseId"])
        for run in list_release_runs(config, repo)
        if run.get("databaseId") is not None
    }
    dispatched_after = datetime.now(timezone.utc)

    command = [
        "workflow",
        "run",
        config.workflow,
        "--repo",
        f"{config.org}/{repo}",
    ]
    for field in build_dispatch_fields(
        tag,
        child_dry_run,
        merge_workflow_fields(repo, shared_fields, repo_fields),
    ):
        command.extend(["--field", field])

    run_gh(command)

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
    repo_fields: dict[str, list[str]] | None = None,
    shared_fields: list[str] | None = None,
) -> int:
    if not repos:
        return 0

    print("")
    print("==========================================")
    print(f"  {title}")
    print("==========================================")

    succeeded = 0
    for repo in repos:
        full_repo = f"{config.org}/{repo}"
        try:
            if not child_dry_run and release_exists(config, repo, tag):
                print(f"--- Skipping: {full_repo} already has release {tag} ---")
                succeeded += 1
                continue

            run_id = dispatch_repo(
                config,
                repo,
                tag,
                child_dry_run,
                repo_fields,
                shared_fields,
            )
            watch_repo(config, repo, run_id)
            succeeded += 1
        except (ReleaseError, subprocess.CalledProcessError) as exc:
            raise ReleaseError(
                "Release failed",
                f"{full_repo} failed during {title}; stopping before remaining repos. "
                f"Completed {succeeded} / {len(repos)} in this phase. {exc}",
            ) from exc

    return succeeded


def dispatch_release_plan(
    config: ReleaseConfig,
    plan: ReleasePlan,
    tag: str,
    child_dry_run: bool,
    repo_fields: dict[str, list[str]] | None = None,
    module_fields: list[str] | None = None,
    coordinator_fields: list[str] | None = None,
    dependency_fields: list[str] | None = None,
) -> None:
    succeeded = 0
    if plan.dependency_selected and config.dependency_repo:
        succeeded += release_phase(
            dependency_release_config(config),
            "Dependency release",
            [config.dependency_repo],
            tag,
            child_dry_run,
            repo_fields,
            dependency_fields,
        )

    succeeded += release_phase(
        config,
        "Module releases",
        plan.module_repos,
        tag,
        child_dry_run,
        repo_fields,
        module_fields,
    )
    if plan.coordinator_selected:
        succeeded += release_phase(
            config,
            "Coordinator release",
            [config.coordinator_repo],
            tag,
            child_dry_run,
            repo_fields,
            coordinator_fields,
        )

    print("")
    print("==========================================")
    print(f"  Completed: {succeeded} / {plan.total()}")
    print("==========================================")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coordinate pack-wide release dispatches.")
    parser.add_argument("--org", required=True, help="GitHub org that owns the pack repos.")
    parser.add_argument("--team", required=True, help="Thunderstore team / repo prefix.")
    parser.add_argument("--coordinator-repo", required=True, help="Coordinator repo name.")
    parser.add_argument("--dependency-repo", default=None, help="Optional shared dependency repo released before modules.")
    parser.add_argument("--dependency-org", default=None, help="GitHub org for --dependency-repo. Defaults to --org.")
    parser.add_argument("--tag", required=True, help="Release version tag.")
    parser.add_argument("--targets", nargs="?", default="", const="", help="Comma-separated release targets. Blank means all.")
    parser.add_argument("--child-dry-run", default="false", help="Pass dry-run mode to child release workflows.")
    parser.add_argument("--plan-only", action="store_true", help="Validate and print the plan without dispatching.")
    parser.add_argument("--root", default=str(ROOT_DIR), help="Shell repo root. Defaults to parent of ModpackTools/.")
    parser.add_argument("--workflow", default="release.yaml", help="Child workflow filename.")
    parser.add_argument("--branch", default="main", help="Child workflow branch.")
    parser.add_argument(
        "--repo-field",
        action="append",
        default=[],
        help="Repo-specific workflow_dispatch field in repo:key=value format. May be repeated.",
    )
    parser.add_argument(
        "--module-field",
        action="append",
        default=[],
        help="workflow_dispatch field sent to every selected module repo in key=value format. May be repeated.",
    )
    parser.add_argument(
        "--coordinator-field",
        action="append",
        default=[],
        help="workflow_dispatch field sent to the coordinator repo in key=value format. May be repeated.",
    )
    parser.add_argument(
        "--pin-coordinator-module-deps",
        action="store_true",
        help="Pin selected coordinator module dependencies to the release tag using the dependency-pins workflow field.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = ReleaseConfig(
        org=args.org,
        team=args.team,
        coordinator_repo=args.coordinator_repo,
        dependency_repo=args.dependency_repo,
        dependency_org=args.dependency_org,
        root=Path(args.root).resolve(),
        workflow=args.workflow,
        branch=args.branch,
    )
    child_dry_run = parse_bool(args.child_dry_run)

    try:
        repo_fields = parse_repo_fields(args.repo_field)
        module_fields = parse_workflow_fields(args.module_field)
        coordinator_fields = parse_workflow_fields(args.coordinator_field)
        plan = build_release_plan(config, args.tag, args.targets)
        if plan.dependency_selected:
            enforce_dependency_lib_version(module_fields, args.tag, "Module")
            enforce_dependency_lib_version(coordinator_fields, args.tag, "Coordinator")
        if args.pin_coordinator_module_deps:
            dependency_pin_field = build_coordinator_dependency_pin_field(plan.module_repos, args.tag)
            if dependency_pin_field is not None:
                coordinator_fields.append(dependency_pin_field)
        print_plan(plan, config)
        if not args.plan_only:
            dispatch_release_plan(
                config,
                plan,
                args.tag,
                child_dry_run,
                repo_fields,
                module_fields,
                coordinator_fields,
                None,
            )
        return 0
    except ReleaseError as exc:
        print(f"::error title={exc.title}::{exc.message}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"::error title=GitHub CLI failed::gh exited with {exc.returncode}", file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
