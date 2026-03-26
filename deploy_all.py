"""
Full local deployment: assets, manifests, symlinks, and git hooks.
Orchestrates all deploy_* scripts.

Usage: python deploy_all.py [--overwrite] [--profile NAME]
"""

import os
import sys
import subprocess
from deploy_common import base_parser, SETUP_DIR


STEPS = [
    ("deploy_assets.py", "Copying assets (icon.png, LICENSE)"),
    ("deploy_manifests.py", "Generating manifests"),
    ("deploy_links.py", "Creating symlinks"),
    ("deploy_hooks.py", "Configuring git hooks"),
]


def main():
    parser = base_parser("Full local deployment for all mods")
    args = parser.parse_args()

    print("\n==========================================================")
    print("  Adamant Modpack - Full Local Deployment")
    print(f"  Profile: {args.profile}")
    print(f"  Overwrite: {args.overwrite}")
    print("==========================================================\n")

    passthrough = []
    if args.overwrite:
        passthrough.append("--overwrite")
    if args.profile != "h2-dev":
        passthrough.extend(["--profile", args.profile])

    for script, label in STEPS:
        print(f">>> {label}...")
        result = subprocess.run(
            [sys.executable, os.path.join(SETUP_DIR, script)] + passthrough
        )
        if result.returncode != 0:
            print(f"ERROR: {script} failed with exit code {result.returncode}")
            sys.exit(result.returncode)

    print("==========================================================")
    print("  Full deployment complete.")
    print("==========================================================\n")


if __name__ == "__main__":
    main()
