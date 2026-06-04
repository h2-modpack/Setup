#!/usr/bin/env python3
"""Tests for deploy/deploy_assets.py."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
DEPLOY_DIR = TOOLS_DIR / "deploy"
if str(DEPLOY_DIR) not in sys.path:
    sys.path.insert(0, str(DEPLOY_DIR))

import deploy_assets  # noqa: E402


def make_package(root: Path) -> Path:
    package = root / "Package"
    (package / "src").mkdir(parents=True)
    (package / "icon.png").write_bytes(b"root-icon")
    (package / "LICENSE").write_text("root license\n", encoding="utf-8")
    return package


def test_stage_package_assets_copies_root_assets_to_src() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        package = make_package(Path(tmp))

        copied = deploy_assets.stage_package_assets(str(package), overwrite=False)

        assert copied
        assert (package / "src" / "icon.png").read_bytes() == b"root-icon"
        assert (package / "src" / "LICENSE").read_text(encoding="utf-8") == "root license\n"


def test_stage_package_assets_respects_existing_files_without_overwrite() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        package = make_package(Path(tmp))
        (package / "src" / "icon.png").write_bytes(b"existing-icon")
        (package / "src" / "LICENSE").write_text("existing license\n", encoding="utf-8")

        copied = deploy_assets.stage_package_assets(str(package), overwrite=False)

        assert not copied
        assert (package / "src" / "icon.png").read_bytes() == b"existing-icon"
        assert (package / "src" / "LICENSE").read_text(encoding="utf-8") == "existing license\n"


def test_stage_package_assets_overwrites_existing_files_when_requested() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        package = make_package(Path(tmp))
        (package / "src" / "icon.png").write_bytes(b"existing-icon")
        (package / "src" / "LICENSE").write_text("existing license\n", encoding="utf-8")

        copied = deploy_assets.stage_package_assets(str(package), overwrite=True)

        assert copied
        assert (package / "src" / "icon.png").read_bytes() == b"root-icon"
        assert (package / "src" / "LICENSE").read_text(encoding="utf-8") == "root license\n"


def main() -> int:
    tests = [
        test_stage_package_assets_copies_root_assets_to_src,
        test_stage_package_assets_respects_existing_files_without_overwrite,
        test_stage_package_assets_overwrites_existing_files_when_requested,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} deploy_assets tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
