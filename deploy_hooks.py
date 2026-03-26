"""
Configures git to use .githooks/ for all mods that have that directory.
Usage: python deploy_hooks.py [--overwrite] [--profile NAME]
"""

import os
import subprocess
from deploy_common import discover_mods, base_parser, ROOT_DIR


def configure_hooks(repo_dir, overwrite):
    githooks_dir = os.path.join(repo_dir, ".githooks")
    if not os.path.isdir(githooks_dir):
        return False

    # Check if already configured
    try:
        result = subprocess.run(
            ["git", "config", "core.hooksPath"],
            cwd=repo_dir, capture_output=True, text=True
        )
        if result.stdout.strip() == ".githooks" and not overwrite:
            return False
    except Exception:
        pass

    subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=repo_dir, check=True)
    return True


def main():
    parser = base_parser("Configure git hooks for all mods")
    args = parser.parse_args()

    print(f"\n  Git hooks configuration")
    print(f"  Overwrite: {args.overwrite}\n")

    count = 0

    # Also configure the shell repo itself
    all_dirs = [ROOT_DIR] + discover_mods()

    for repo_dir in all_dirs:
        name = os.path.basename(repo_dir)
        if configure_hooks(repo_dir, args.overwrite):
            print(f"  CONFIGURED: {name}")
            count += 1
        else:
            print(f"  SKIP: {name}")

    print(f"\nDone. {count} repos configured.\n")


if __name__ == "__main__":
    main()
