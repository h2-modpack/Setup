"""
Generate manifest.json from thunderstore.toml for local deployment.
"""

import os

from .common import discover_packages
from .manifest_writer import write_manifest


def generate_manifest_for_package(package_dir, overwrite):
    """Generate src/manifest.json for one package if needed."""
    toml_path = os.path.join(package_dir, "thunderstore.toml")
    output_path = os.path.join(package_dir, "src", "manifest.json")
    package_name = os.path.basename(package_dir)

    if os.path.exists(output_path) and not overwrite:
        print(f"  SKIP (exists): {package_name}/src/manifest.json")
        return False

    print(f"--- {package_name} ---")
    write_manifest(toml_path, output_path)
    print(f"  Generated manifest: {output_path}")
    return True


def deploy(overwrite):
    print("\n  Manifest generation")
    print(f"  Overwrite: {overwrite}\n")

    count = 0
    for package_dir in discover_packages():
        if generate_manifest_for_package(package_dir, overwrite):
            count += 1

    print(f"\nDone. {count} manifests generated.\n")
    return count
