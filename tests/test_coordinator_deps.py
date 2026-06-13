#!/usr/bin/env python3
"""Tests for new_module/coordinator_deps.py."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
NEW_MODULE_DIR = TOOLS_DIR / "new_module"
if str(NEW_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(NEW_MODULE_DIR))

import coordinator_deps  # noqa: E402


def write_package_toml(path: Path, *, namespace: str, name: str, version: str = "1.0.0") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
[package]
namespace = "{namespace}"
name = "{name}"
versionNumber = "{version}"
""".lstrip(),
        encoding="utf-8",
    )


def write_module(root: Path, folder: str, *, namespace: str, name: str, version: str) -> None:
    module_dir = root / "Submodules" / folder
    module_dir.mkdir(parents=True)
    write_package_toml(
        module_dir / "thunderstore.toml",
        namespace=namespace,
        name=name,
        version=version,
    )


def write_gitmodules(root: Path, paths: list[str]) -> None:
    root.joinpath(".gitmodules").write_text(
        "".join(
            f'[submodule "{path}"]\n'
            f"\tpath = {path}\n"
            f"\turl = https://example.invalid/{path.split('/')[-1]}.git\n"
            for path in paths
        ),
        encoding="utf-8",
    )


def with_temp_roots(func) -> None:
    old_root = coordinator_deps.ROOT_DIR
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Submodules").mkdir()
            coordinator_deps.ROOT_DIR = str(root)
            func(root)
    finally:
        coordinator_deps.ROOT_DIR = old_root


def test_update_coordinator_deps_replaces_managed_block_only() -> None:
    def run(root: Path) -> None:
        coordinator = root / "adamantSpeedrun-Speedrun_Modpack" / "thunderstore.toml"
        coordinator.parent.mkdir()
        coordinator.write_text(
            """
[package]
namespace = "adamantSpeedrun"
name = "Speedrun_Modpack"
versionNumber = "1.0.0"

[package.dependencies]
adamant-ModpackLib = "1.0.0"
# -- submodules-start --
old-package = "0.0.1"
# -- submodules-end --

[build]
icon = "./icon.png"
""".lstrip(),
            encoding="utf-8",
        )
        write_module(root, "adamantSpeedrun-Zeta", namespace="adamantSpeedrun", name="Zeta", version="2.0.0")
        write_module(root, "adamantSpeedrun-Alpha", namespace="adamantSpeedrun", name="Alpha", version="1.2.3")
        write_gitmodules(
            root,
            [
                "adamantSpeedrun-Speedrun_Modpack",
                "Submodules/adamantSpeedrun-Zeta",
                "Submodules/adamantSpeedrun-Alpha",
            ],
        )

        coordinator_deps.update_coordinator_deps()

        text = coordinator.read_text(encoding="utf-8")
        expected = """
[package.dependencies]
adamant-ModpackLib = "1.0.0"
# -- submodules-start --
adamantSpeedrun-Alpha = "1.2.3"
adamantSpeedrun-Zeta = "2.0.0"
# -- submodules-end --

[build]
""".lstrip()
        if expected not in text:
            raise AssertionError(text)
        if "old-package" in text:
            raise AssertionError("stale managed dependency was not removed")

    with_temp_roots(run)


def test_update_coordinator_deps_inserts_block_when_missing() -> None:
    def run(root: Path) -> None:
        coordinator = root / "adamantRunDirector-RunDirector_Modpack" / "thunderstore.toml"
        coordinator.parent.mkdir()
        coordinator.write_text(
            """
[package]
namespace = "adamantRunDirector"
name = "RunDirector_Modpack"
versionNumber = "1.0.0"

[package.dependencies]
adamant-ModpackLib = "1.0.0"

[publish]
repository = "https://thunderstore.io"
""".lstrip(),
            encoding="utf-8",
        )
        write_module(root, "adamantRunDirector-GodPool", namespace="adamantRunDirector", name="GodPool", version="0.0.1")
        write_gitmodules(
            root,
            [
                "adamantRunDirector-RunDirector_Modpack",
                "Submodules/adamantRunDirector-GodPool",
            ],
        )

        coordinator_deps.update_coordinator_deps()

        text = coordinator.read_text(encoding="utf-8")
        expected = """
[package.dependencies]
adamant-ModpackLib = "1.0.0"

# -- submodules-start --
adamantRunDirector-GodPool = "0.0.1"
# -- submodules-end --

[publish]
""".lstrip()
        if expected not in text:
            raise AssertionError(text)

    with_temp_roots(run)


def main() -> int:
    tests = [
        test_update_coordinator_deps_replaces_managed_block_only,
        test_update_coordinator_deps_inserts_block_when_missing,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} coordinator_deps tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
