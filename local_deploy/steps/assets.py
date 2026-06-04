"""
Stage each package's root-level assets into src/ for local deployment.
"""

import os
import shutil

from .common import discover_packages


ASSETS = ["icon.png", "LICENSE"]


def stage_package_assets(package_dir, overwrite):
    """Copy root package assets into src/ for local deployment."""
    package_name = os.path.basename(package_dir)
    src_dir = os.path.join(package_dir, "src")
    copied_any = False

    for asset in ASSETS:
        source = os.path.join(package_dir, asset)
        dest = os.path.join(src_dir, asset)

        if not os.path.exists(source):
            print(f"  WARNING: {asset} not found in {package_name}/")
            continue

        if os.path.exists(dest) and not overwrite:
            continue

        shutil.copy2(source, dest)
        copied_any = True

    return copied_any


def deploy(overwrite):
    print("\n  Asset deployment")
    print(f"  Overwrite: {overwrite}\n")

    count = 0
    for package_dir in discover_packages():
        package_name = os.path.basename(package_dir)
        if stage_package_assets(package_dir, overwrite):
            print(f"  COPIED assets -> {package_name}/src/")
            count += 1
        else:
            print(f"  SKIP (exists): {package_name}")

    print(f"\nDone. {count} packages updated.\n")
    return count
