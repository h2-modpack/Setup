#!/usr/bin/env python3
"""Validate modpack platform dependency pins.

Run from a shell repo that has Setup checked out as a submodule. Lib and
Framework own their package versions in their checked-out thunderstore.toml
files; the shell repo owns the assembled snapshot through submodule pointers.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    print("Python 3.11+ is required for tomllib.", file=sys.stderr)
    sys.exit(2)


SETUP_DIR = Path(__file__).resolve().parent
ROOT = SETUP_DIR.parent


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_toml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{rel(path)} does not exist")
    with path.open("rb") as handle:
        return tomllib.load(handle)


def package_name(path: Path, data: dict) -> str:
    package = data.get("package", {})
    namespace = package.get("namespace")
    name = package.get("name")
    if not namespace or not name:
        raise ValueError(f"{rel(path)} is missing package.namespace or package.name")
    return f"{namespace}-{name}"


def package_version(path: Path, data: dict) -> str:
    version = data.get("package", {}).get("versionNumber")
    if not version:
        raise ValueError(f"{rel(path)} is missing package.versionNumber")
    return version


def dependency_version(data: dict, dependency: str) -> str | None:
    return data.get("package", {}).get("dependencies", {}).get(dependency)


def check_dependency(errors: list[str], path: Path, data: dict, dependency: str, expected: str) -> None:
    actual = dependency_version(data, dependency)
    if actual == expected:
        return

    if actual is None:
        errors.append(f"{rel(path)} is missing dependency {dependency} = \"{expected}\"")
    else:
        errors.append(
            f"{rel(path)} has {dependency} = \"{actual}\"; expected \"{expected}\""
        )


def find_core_toml() -> Path:
    for entry in sorted(ROOT.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue

        toml_path = entry / "thunderstore.toml"
        if not toml_path.exists():
            continue

        data = load_toml(toml_path)
        name = data.get("package", {}).get("name", "")
        if name.endswith("Core"):
            return toml_path

    raise FileNotFoundError("No root-level Core thunderstore.toml found")


def main() -> int:
    lib_path = ROOT / "adamant-ModpackLib" / "thunderstore.toml"
    framework_path = ROOT / "adamant-ModpackFramework" / "thunderstore.toml"
    module_root = ROOT / "Submodules"

    try:
        lib_data = load_toml(lib_path)
        framework_data = load_toml(framework_path)
        core_path = find_core_toml()
        core_data = load_toml(core_path)
        module_paths = sorted(module_root.glob("*/thunderstore.toml"))
        lib_name = package_name(lib_path, lib_data)
        framework_name = package_name(framework_path, framework_data)
        lib_version = package_version(lib_path, lib_data)
        framework_version = package_version(framework_path, framework_data)
    except (OSError, ValueError) as exc:
        print(f"::error::{exc}")
        return 1

    errors: list[str] = []
    check_dependency(errors, framework_path, framework_data, lib_name, lib_version)
    check_dependency(errors, core_path, core_data, lib_name, lib_version)
    check_dependency(errors, core_path, core_data, framework_name, framework_version)

    loaded_modules: list[tuple[str, str]] = []
    for module_path in module_paths:
        try:
            module_data = load_toml(module_path)
            module_name = package_name(module_path, module_data)
            module_version = package_version(module_path, module_data)
            loaded_modules.append((module_name, module_version))
            check_dependency(errors, module_path, module_data, lib_name, lib_version)
            check_dependency(errors, core_path, core_data, module_name, module_version)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))

    print("Platform version snapshot:")
    print(f"  {lib_name} {lib_version}")
    print(f"  {framework_name} {framework_version}")
    print(f"  {package_name(core_path, core_data)} {package_version(core_path, core_data)}")
    print("  Modules:")
    if loaded_modules:
        for module_name, module_version in loaded_modules:
            print(f"    {module_name} {module_version}")
    else:
        print("    (none)")

    if errors:
        print("")
        print("Platform dependency validation failed:")
        for error in errors:
            print(f"::error::{error}")
        return 1

    print("")
    print("Platform dependency versions are coherent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
