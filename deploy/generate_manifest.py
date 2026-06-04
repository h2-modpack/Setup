#!/usr/bin/env python3
"""Reads a thunderstore.toml and generates a manifest.json for local deployment.

Usage: python generate_manifest.py <path_to_thunderstore.toml> <output_manifest.json>
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    print("Python 3.11+ is required for tomllib.", file=sys.stderr)
    sys.exit(2)


def _require_string(package: dict, key: str, toml_path: Path) -> str:
    value = package.get(key)
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{toml_path} is missing package.{key}")
    return value


def parse_toml(toml_path: str | os.PathLike[str]) -> dict:
    """Reads thunderstore.toml and returns manifest fields."""
    path = Path(toml_path)
    with path.open("rb") as handle:
        data = tomllib.load(handle)

    package = data.get("package")
    if not isinstance(package, dict):
        raise ValueError(f"{path} is missing [package]")

    namespace = _require_string(package, "namespace", path)
    name = _require_string(package, "name", path)
    description = _require_string(package, "description", path)
    version = _require_string(package, "versionNumber", path)
    website_url = package.get("websiteUrl", "")
    if not isinstance(website_url, str):
        raise ValueError(f"{path} package.websiteUrl must be a string when provided")

    raw_dependencies = package.get("dependencies", {})
    if not isinstance(raw_dependencies, dict):
        raise ValueError(f"{path} package.dependencies must be a table when provided")

    dependencies = []
    for dependency, dependency_version in raw_dependencies.items():
        if not isinstance(dependency_version, str) or dependency_version == "":
            raise ValueError(f"{path} dependency {dependency} must have a non-empty string version")
        dependencies.append(f"{dependency}-{dependency_version}")

    return {
        "namespace": namespace,
        "name": name,
        "description": description,
        "version_number": version,
        "dependencies": dependencies,
        "website_url": website_url,
        "FullName": f"{namespace}-{name}",
    }


def write_manifest(toml_path: str | os.PathLike[str], output_path: str | os.PathLike[str]) -> dict:
    """Generate and write manifest.json content for one package."""
    manifest = parse_toml(toml_path)
    path = Path(output_path)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return manifest


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python generate_manifest.py <thunderstore.toml> <output_manifest.json>")
        return 1

    toml_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not toml_path.is_file():
        print(f"Error: '{toml_path}' not found.")
        return 1

    try:
        write_manifest(toml_path, output_path)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"Error: {exc}")
        return 1

    print(f"  Generated manifest: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
