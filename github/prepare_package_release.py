#!/usr/bin/env python3
"""Prepare package release files from conventional commits.

Run from a package repo checkout. The script intentionally mutates only the
package-local release files; workflow policy still owns build, publish, commit,
tag, and push behavior.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
CONVENTIONAL_PATTERN = re.compile(r"^([A-Za-z]+)(?:\(([^)]+)\))?(!)?: (.+)$")
BREAKING_PATTERN = re.compile(r"BREAKING[ -]CHANGE:\s*(.+)", re.IGNORECASE | re.DOTALL)
VERSION_LINE_PATTERN = re.compile(r'^(versionNumber\s*=\s*)".*"$', re.MULTILINE)

SECTION_TITLES = {
    "feat": "Added",
    "fix": "Fixed",
    "perf": "Performance",
    "refactor": "Changed",
    "docs": "Documentation",
}
SECTION_ORDER = [
    "Breaking Changes",
    "Added",
    "Fixed",
    "Performance",
    "Changed",
    "Documentation",
]


class ReleasePrepError(Exception):
    def __init__(self, title: str, message: str):
        super().__init__(message)
        self.title = title
        self.message = message


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str
    body: str


@dataclass(frozen=True)
class ChangelogEntry:
    section: str
    text: str


def run_git(repo: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def validate_tag(tag: str) -> None:
    if not VERSION_PATTERN.match(tag or ""):
        raise ReleasePrepError(
            "Invalid package version number",
            "Version numbers must follow the Major.Minor.Patch format (e.g. 1.45.320).",
        )


def find_previous_tag(repo: Path, release_tag: str) -> str | None:
    tags = run_git(repo, ["tag", "--merged", "HEAD", "--sort=-v:refname"]).splitlines()
    for tag in tags:
        normalized = tag.strip()
        if VERSION_PATTERN.match(normalized) and normalized != release_tag:
            return normalized
    return None


def read_commits(repo: Path, previous_tag: str | None) -> list[Commit]:
    revision = f"{previous_tag}..HEAD" if previous_tag else "HEAD"
    raw = run_git(repo, ["log", "--format=%H%x00%s%x00%b%x1e", revision])
    commits: list[Commit] = []
    for record in raw.split("\x1e"):
        record = record.rstrip("\n")
        if not record:
            continue
        parts = record.split("\x00", 2)
        if len(parts) != 3:
            continue
        commits.append(Commit(sha=parts[0], subject=parts[1], body=parts[2].strip()))
    return commits


def _first_line(value: str) -> str:
    return (value or "").strip().splitlines()[0].strip()


def _entry_text(scope: str | None, description: str, sha: str) -> str:
    text = description.strip()
    if scope:
        text = f"{scope.strip()}: {text}"
    return f"{text} ({sha[:7]})"


def parse_commits(commits: list[Commit]) -> list[ChangelogEntry]:
    entries: list[ChangelogEntry] = []
    for commit in commits:
        match = CONVENTIONAL_PATTERN.match(commit.subject)
        if not match:
            continue

        commit_type, scope, bang, description = match.groups()
        commit_type = commit_type.lower()
        breaking_match = BREAKING_PATTERN.search(commit.body)
        if bang or breaking_match:
            breaking_text = _first_line(breaking_match.group(1)) if breaking_match else description
            entries.append(ChangelogEntry("Breaking Changes", _entry_text(scope, breaking_text, commit.sha)))

        section = SECTION_TITLES.get(commit_type)
        if section:
            entries.append(ChangelogEntry(section, _entry_text(scope, description, commit.sha)))

    return entries


def render_section(tag: str, release_date: date, entries: list[ChangelogEntry], allow_empty: bool) -> str:
    grouped: dict[str, list[str]] = {}
    for entry in entries:
        grouped.setdefault(entry.section, []).append(entry.text)

    if not grouped:
        if not allow_empty:
            raise ReleasePrepError(
                "Empty changelog",
                "No visible conventional commits found. Pass --allow-empty to release without user-facing changes.",
            )
        grouped["Changed"] = ["No user-facing changes."]

    lines = [f"## [{tag}] - {release_date.isoformat()}", ""]
    for section in SECTION_ORDER:
        items = grouped.get(section)
        if not items:
            continue
        lines.append(f"### {section}")
        lines.append("")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def update_changelog(content: str, tag: str, section: str) -> str:
    if re.search(rf"^## \[{re.escape(tag)}\](?:\s|-)", content, re.MULTILINE):
        raise ReleasePrepError("Duplicate changelog section", f"CHANGELOG.md already has a section for {tag}.")

    marker = re.search(r"^## \[Unreleased\]\s*$", content, re.MULTILINE)
    if not marker:
        raise ReleasePrepError("Missing changelog section", "CHANGELOG.md must contain '## [Unreleased]'.")

    insert_at = marker.end()
    tail = content[insert_at:].lstrip()
    return content[:insert_at].rstrip() + "\n\n" + section.rstrip() + "\n\n" + tail


def update_thunderstore_config(content: str, tag: str) -> str:
    updated, count = VERSION_LINE_PATTERN.subn(rf'\g<1>"{tag}"', content, count=1)
    if count != 1:
        raise ReleasePrepError(
            "Missing Thunderstore version",
            "thunderstore.toml must contain exactly one package versionNumber line.",
        )
    return updated


def prepare_release(
    repo: Path,
    tag: str,
    changelog_path: Path,
    thunderstore_path: Path,
    allow_empty: bool,
    release_date: date,
) -> None:
    validate_tag(tag)
    previous_tag = find_previous_tag(repo, tag)
    commits = read_commits(repo, previous_tag)
    entries = parse_commits(commits)
    section = render_section(tag, release_date, entries, allow_empty)

    changelog = changelog_path.read_text(encoding="utf-8")
    changelog_path.write_text(update_changelog(changelog, tag, section), encoding="utf-8", newline="\n")

    thunderstore = thunderstore_path.read_text(encoding="utf-8")
    thunderstore_path.write_text(update_thunderstore_config(thunderstore, tag), encoding="utf-8", newline="\n")

    print(f"Prepared release {tag}")
    print(f"Previous tag: {previous_tag or '(none)'}")
    print(f"Changelog entries: {len(entries)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="Release version tag.")
    parser.add_argument("--repo-root", default=".", help="Package repo root. Defaults to current directory.")
    parser.add_argument("--changelog", default="CHANGELOG.md", help="Changelog path relative to repo root.")
    parser.add_argument("--thunderstore-config", default="thunderstore.toml", help="Thunderstore config path.")
    parser.add_argument("--allow-empty", action="store_true", help="Allow releases with no visible changelog entries.")
    parser.add_argument("--date", default=None, help="Release date override in YYYY-MM-DD form, for tests/backfills.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    release_date = date.fromisoformat(args.date) if args.date else date.today()

    try:
        prepare_release(
            repo=repo,
            tag=args.tag,
            changelog_path=repo / args.changelog,
            thunderstore_path=repo / args.thunderstore_config,
            allow_empty=args.allow_empty,
            release_date=release_date,
        )
        return 0
    except ReleasePrepError as exc:
        print(f"::error title={exc.title}::{exc.message}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"::error title=Git failed::git exited with {exc.returncode}", file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
