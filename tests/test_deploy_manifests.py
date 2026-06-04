#!/usr/bin/env python3
"""Tests for manifest generation deploy helpers."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
DEPLOY_DIR = TOOLS_DIR / "deploy"
if str(DEPLOY_DIR) not in sys.path:
    sys.path.insert(0, str(DEPLOY_DIR))

from steps import manifest_writer, manifests  # noqa: E402


PACKAGE_TOML = """
[package]
namespace = "adamantSpeedrun"
name = "LiveSplit"
description = "Timer tools"
versionNumber = "1.2.3"
websiteUrl = "https://github.com/h2pack-speedrun/adamantSpeedrun-LiveSplit"

[package.dependencies]
adamant-ModpackLib = "1.1.0"
Other-Team = "2.0.0"
""".lstrip()


def make_package(root: Path) -> Path:
    package = root / "Package"
    (package / "src").mkdir(parents=True)
    (package / "thunderstore.toml").write_text(PACKAGE_TOML, encoding="utf-8")
    return package


def test_write_manifest_outputs_local_manifest_shape() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        package = make_package(Path(tmp))
        output = package / "src" / "manifest.json"

        manifest = manifest_writer.write_manifest(package / "thunderstore.toml", output)
        written = json.loads(output.read_text(encoding="utf-8"))

        expected = {
            "namespace": "adamantSpeedrun",
            "name": "LiveSplit",
            "description": "Timer tools",
            "version_number": "1.2.3",
            "dependencies": [
                "adamant-ModpackLib-1.1.0",
                "Other-Team-2.0.0",
            ],
            "website_url": "https://github.com/h2pack-speedrun/adamantSpeedrun-LiveSplit",
            "FullName": "adamantSpeedrun-LiveSplit",
        }
        assert manifest == expected
        assert written == expected


def test_generate_manifest_for_package_skips_existing_without_overwrite() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        package = make_package(Path(tmp))
        output = package / "src" / "manifest.json"
        output.write_text('{"existing": true}\n', encoding="utf-8")

        generated = manifests.generate_manifest_for_package(str(package), overwrite=False)

        assert not generated
        assert json.loads(output.read_text(encoding="utf-8")) == {"existing": True}


def test_generate_manifest_for_package_overwrites_when_requested() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        package = make_package(Path(tmp))
        output = package / "src" / "manifest.json"
        output.write_text('{"existing": true}\n', encoding="utf-8")

        generated = manifests.generate_manifest_for_package(str(package), overwrite=True)

        assert generated
        assert json.loads(output.read_text(encoding="utf-8"))["FullName"] == "adamantSpeedrun-LiveSplit"


def main() -> int:
    tests = [
        test_write_manifest_outputs_local_manifest_shape,
        test_generate_manifest_for_package_skips_existing_without_overwrite,
        test_generate_manifest_for_package_overwrites_when_requested,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} deploy manifests tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
