"""
Configure git to use .githooks/ for package repos and the shell repo.
"""

import os
import subprocess

from .common import ROOT_DIR, discover_packages


def configure_hooks(repo_dir, overwrite):
    githooks_dir = os.path.join(repo_dir, ".githooks")
    if not os.path.isdir(githooks_dir):
        return False

    try:
        result = subprocess.run(
            ["git", "config", "core.hooksPath"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        )
        if result.stdout.strip() == ".githooks" and not overwrite:
            return False
    except Exception:
        pass

    subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=repo_dir, check=True)
    return True


def deploy(overwrite):
    print("\n  Git hooks configuration")
    print(f"  Overwrite: {overwrite}\n")

    count = 0
    for repo_dir in [ROOT_DIR] + discover_packages():
        name = os.path.basename(repo_dir)
        if configure_hooks(repo_dir, overwrite):
            print(f"  CONFIGURED: {name}")
            count += 1
        else:
            print(f"  SKIP: {name}")

    print(f"\nDone. {count} repos configured.\n")
    return count
