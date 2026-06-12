#!/usr/bin/env python3
"""Tests for github/check_thunderstore_release.py."""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError


TEST_DIR = Path(__file__).resolve().parent
TOOLS_DIR = TEST_DIR.parent

sys.path.insert(0, str(TOOLS_DIR / "github"))
import check_thunderstore_release as check  # noqa: E402


class FakeResponse:
    def __init__(self, status: int):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def assert_raises(title: str, func) -> check.ThunderstoreCheckError:
    try:
        func()
    except check.ThunderstoreCheckError as exc:
        assert_equal(exc.title, title, "error title")
        return exc
    raise AssertionError(f"expected ThunderstoreCheckError titled {title!r}")


def write_toml(root: Path, content: str) -> Path:
    path = root / "thunderstore.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_read_package_identity_uses_manifest_fields() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = write_toml(
            Path(tmp),
            """
[package]
namespace = "adamant"
name = "ModpackLib"
versionNumber = "3.0.0"

[publish]
repository = "https://example.test/"
""",
        )

        identity = check.read_package_identity(path, "3.0.0")
        assert_equal(identity.repository, "https://example.test", "repository")
        assert_equal(identity.namespace, "adamant", "namespace")
        assert_equal(identity.name, "ModpackLib", "name")
        assert_equal(identity.version, "3.0.0", "version")
        assert_equal(
            check.release_url(identity),
            "https://example.test/api/experimental/package/adamant/ModpackLib/3.0.0/",
            "release url",
        )


def test_read_package_identity_rejects_tag_mismatch() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = write_toml(Path(tmp), '[package]\nnamespace = "Team"\nname = "Package"\nversionNumber = "1.0.0"\n')
        assert_raises("Thunderstore version mismatch", lambda: check.read_package_identity(path, "1.0.1"))


def test_thunderstore_release_exists_returns_true_for_success() -> None:
    identity = check.PackageIdentity("https://example.test", "Team", "Package", "1.0.0")
    old_urlopen = check.urlopen

    def fake_urlopen(_request, timeout):
        assert_equal(timeout, 20, "timeout")
        return FakeResponse(200)

    try:
        check.urlopen = fake_urlopen
        assert_equal(check.thunderstore_release_exists(identity), True, "published")
    finally:
        check.urlopen = old_urlopen


def test_thunderstore_release_exists_returns_false_for_missing_package() -> None:
    identity = check.PackageIdentity("https://example.test", "Team", "Package", "1.0.0")
    old_urlopen = check.urlopen

    def fake_urlopen(_request, timeout):
        assert_equal(timeout, 20, "timeout")
        raise HTTPError("https://example.test", 404, "Not Found", {}, io.BytesIO())

    try:
        check.urlopen = fake_urlopen
        assert_equal(check.thunderstore_release_exists(identity), False, "published")
    finally:
        check.urlopen = old_urlopen


def test_thunderstore_release_exists_rejects_api_failure() -> None:
    identity = check.PackageIdentity("https://example.test", "Team", "Package", "1.0.0")
    old_urlopen = check.urlopen

    def fake_urlopen(_request, timeout):
        assert_equal(timeout, 20, "timeout")
        raise HTTPError("https://example.test", 500, "Server Error", {}, io.BytesIO())

    try:
        check.urlopen = fake_urlopen
        assert_raises("Thunderstore check failed", lambda: check.thunderstore_release_exists(identity))
    finally:
        check.urlopen = old_urlopen


def test_write_github_output_writes_package_state() -> None:
    identity = check.PackageIdentity("https://example.test", "Team", "Package", "1.0.0")
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "output"
        check.write_github_output(str(output), identity, True)
        assert_equal(output.read_text(encoding="utf-8"), "published=true\npackage=Team-Package-1.0.0\n", "output")


def main() -> int:
    tests = [
        test_read_package_identity_uses_manifest_fields,
        test_read_package_identity_rejects_tag_mismatch,
        test_thunderstore_release_exists_returns_true_for_success,
        test_thunderstore_release_exists_returns_false_for_missing_package,
        test_thunderstore_release_exists_rejects_api_failure,
        test_write_github_output_writes_package_state,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} check_thunderstore_release tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
