"""
Full local deployment: staged package assets, manifests, profile links/copies, and git hooks.

Usage: python deploy_all.py [--overwrite] [--profile NAME]
"""

import sys
from steps import assets, hooks, links, manifests
from steps.common import base_parser


STEPS = [
    ("Staging package assets (icon.png, LICENSE)", lambda args: assets.deploy(args.overwrite)),
    ("Generating manifests", lambda args: manifests.deploy(args.overwrite)),
    ("Deploying profile links", lambda args: links.deploy(args.overwrite, args.profile, args.profile_root, args.link_mode)),
    ("Configuring git hooks", lambda args: hooks.deploy(args.overwrite)),
]


def main():
    parser = base_parser("Full local deployment for all mods")
    args = parser.parse_args()

    print("\n==========================================================")
    print("  Adamant Modpack - Full Local Deployment")
    print(f"  Profile: {args.profile}")
    print(f"  Overwrite: {args.overwrite}")
    print("==========================================================\n")

    for label, deploy_step in STEPS:
        print(f">>> {label}...")
        deploy_step(args)

    print("==========================================================")
    print("  Full deployment complete.")
    print("==========================================================\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
