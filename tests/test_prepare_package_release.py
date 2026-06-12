#!/usr/bin/env python3
"""Tests for github/prepare_package_release.py."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TEST_DIR.parent

sys.path.insert(0, str(TOOLS_DIR / "github"))
import prepare_package_release as prep  # noqa: E402


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def assert_raises(title: str, func) -> prep.ReleasePrepError:
    try:
        func()
    except prep.ReleasePrepError as exc:
        assert_equal(exc.title, title, "error title")
        return exc
    raise AssertionError(f"expected ReleasePrepError titled {title!r}")


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def write(repo: Path, path: str, content: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")


def commit(repo: Path, message: str, body: str | None = None) -> None:
    git(repo, "add", ".")
    args = ["commit", "-m", message]
    if body is not None:
        args.extend(["-m", body])
    git(repo, *args)


def init_repo() -> Path:
    root = Path(tempfile.mkdtemp())
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Test User")
    git(root, "config", "user.email", "test@example.com")
    return root


def test_parse_commits_groups_visible_conventional_types() -> None:
    commits = [
        prep.Commit("111111111111", "feat(ui): add profile button", ""),
        prep.Commit("222222222222", "fix: restore fallback spacing", ""),
        prep.Commit("333333333333", "chore: update tooling", ""),
        prep.Commit("444444444444", "refactor!: remove legacy API", "BREAKING CHANGE: old API removed\n\nMore."),
    ]
    entries = prep.parse_commits(commits)

    assert_equal([entry.section for entry in entries], [
        "Added",
        "Fixed",
        "Breaking Changes",
        "Changed",
    ], "entry sections")
    assert_equal(entries[0].text, "ui: add profile button (1111111)", "scoped entry")
    assert_equal(entries[2].text, "old API removed (4444444)", "breaking entry")


def test_render_section_rejects_empty_without_allow_empty() -> None:
    assert_raises(
        "Empty changelog",
        lambda: prep.render_section("1.2.0", date(2026, 6, 9), [], False),
    )


def test_render_section_allows_empty_release() -> None:
    rendered = prep.render_section("1.2.0", date(2026, 6, 9), [], True)
    if "- No user-facing changes." not in rendered:
        raise AssertionError(f"missing empty-release note:\n{rendered}")


def test_update_changelog_inserts_after_unreleased() -> None:
    updated = prep.update_changelog(
        "# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-01-01\n",
        "1.1.0",
        "## [1.1.0] - 2026-06-09\n\n### Added\n\n- Thing\n",
    )
    expected = "# Changelog\n\n## [Unreleased]\n\n## [1.1.0] - 2026-06-09\n\n### Added\n\n- Thing\n\n## [1.0.0] - 2026-01-01\n"
    assert_equal(updated, expected, "updated changelog")


def test_update_changelog_rejects_duplicate_tag() -> None:
    assert_raises(
        "Duplicate changelog section",
        lambda: prep.update_changelog(
            "# Changelog\n\n## [Unreleased]\n\n## [1.1.0] - 2026-06-09\n",
            "1.1.0",
            "## [1.1.0] - 2026-06-09\n",
        ),
    )


def test_update_thunderstore_config_replaces_version() -> None:
    updated = prep.update_thunderstore_config(
        '[package]\nname = "Package"\nversionNumber = "1.0.0"\n',
        "1.2.0",
    )
    assert_equal(updated, '[package]\nname = "Package"\nversionNumber = "1.2.0"\n', "updated toml")


def test_update_dependency_pins_replaces_matching_table_dependency() -> None:
    updated = prep.update_dependency_pins(
        '\n'.join([
            '[package]',
            '[package.dependencies]',
            'adamant-ModpackLib = "3.0.0"',
            'Other-Team-Package = "1.2.3"',
            '',
        ]),
        [prep.DependencyPin("adamant-ModpackLib", "3.1.0")],
    )
    expected = '\n'.join([
        '[package]',
        '[package.dependencies]',
        'adamant-ModpackLib = "3.1.0"',
        'Other-Team-Package = "1.2.3"',
        '',
    ])
    assert_equal(updated, expected, "dependency pin")


def test_update_dependency_pins_replaces_matching_string_dependency() -> None:
    updated = prep.update_dependency_pins(
        'dependencies = ["h2-modpack-adamant-ModpackLib-3.0.0", "Other-Team-Package-1.2.3"]\n',
        [prep.DependencyPin("h2-modpack-adamant-ModpackLib", "3.1.0")],
    )
    assert_equal(
        updated,
        'dependencies = ["h2-modpack-adamant-ModpackLib-3.1.0", "Other-Team-Package-1.2.3"]\n',
        "string dependency pin",
    )


def test_update_dependency_pins_rejects_missing_dependency() -> None:
    assert_raises(
        "Missing dependency pin",
        lambda: prep.update_dependency_pins(
            'dependencies = ["Other-Team-Package-1.2.3"]\n',
            [prep.DependencyPin("h2-modpack-adamant-ModpackLib", "3.1.0")],
        ),
    )


def test_update_dependency_pins_rejects_duplicate_dependency() -> None:
    assert_raises(
        "Duplicate dependency pin",
        lambda: prep.update_dependency_pins(
            '\n'.join([
                '[package.dependencies]',
                'adamant-ModpackLib = "3.0.0"',
                'adamant-ModpackLib = "3.0.1"',
                '',
            ]),
            [prep.DependencyPin("adamant-ModpackLib", "3.1.0")],
        ),
    )


def test_update_dependency_pins_leaves_unmanaged_dependencies() -> None:
    updated = prep.update_dependency_pins(
        '[package.dependencies]\nManaged-Team-Package = "1.0.0"\nUnmanaged-Team-Package = "9.9.9"\n',
        [prep.DependencyPin("Managed-Team-Package", "1.1.0")],
    )
    assert_equal(
        updated,
        '[package.dependencies]\nManaged-Team-Package = "1.1.0"\nUnmanaged-Team-Package = "9.9.9"\n',
        "unmanaged dependency",
    )


def test_prepare_release_uses_commits_since_previous_tag() -> None:
    repo = init_repo()
    write(repo, "CHANGELOG.md", "# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-01-01\n")
    write(repo, "thunderstore.toml", '[package]\nversionNumber = "1.0.0"\n')
    write(repo, "src/main.lua", "return {}\n")
    commit(repo, "feat: initial package")
    git(repo, "tag", "1.0.0")

    write(repo, "src/main.lua", "return { updated = true }\n")
    commit(repo, "feat(runtime): add setting")
    write(repo, "README.md", "docs\n")
    commit(repo, "docs: update readme")

    prep.prepare_release(
        repo=repo,
        tag="1.1.0",
        changelog_path=repo / "CHANGELOG.md",
        thunderstore_path=repo / "thunderstore.toml",
        release_notes_path=repo / ".release-notes.md",
        dependency_pins=[],
        allow_empty=False,
        release_date=date(2026, 6, 9),
    )

    changelog = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    release_notes = (repo / ".release-notes.md").read_text(encoding="utf-8")
    thunderstore = (repo / "thunderstore.toml").read_text(encoding="utf-8")
    if "## [1.1.0] - 2026-06-09" not in changelog:
        raise AssertionError(changelog)
    if "runtime: add setting" not in changelog:
        raise AssertionError(changelog)
    if "update readme" not in changelog:
        raise AssertionError(changelog)
    if release_notes not in changelog:
        raise AssertionError(release_notes)
    if "## [1.1.0] - 2026-06-09" not in release_notes:
        raise AssertionError(release_notes)
    if "runtime: add setting" not in release_notes:
        raise AssertionError(release_notes)
    if 'versionNumber = "1.1.0"' not in thunderstore:
        raise AssertionError(thunderstore)


def main() -> int:
    tests = [
        test_parse_commits_groups_visible_conventional_types,
        test_render_section_rejects_empty_without_allow_empty,
        test_render_section_allows_empty_release,
        test_update_changelog_inserts_after_unreleased,
        test_update_changelog_rejects_duplicate_tag,
        test_update_thunderstore_config_replaces_version,
        test_update_dependency_pins_replaces_matching_table_dependency,
        test_update_dependency_pins_replaces_matching_string_dependency,
        test_update_dependency_pins_rejects_missing_dependency,
        test_update_dependency_pins_rejects_duplicate_dependency,
        test_update_dependency_pins_leaves_unmanaged_dependencies,
        test_prepare_release_uses_commits_since_previous_tag,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} prepare_package_release tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
