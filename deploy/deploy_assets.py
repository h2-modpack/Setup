"""
Copies icon.png and LICENSE into each mod's src/ folder.
Usage: python deploy_assets.py [--overwrite] [--profile NAME]
"""

import os
import shutil
from deploy_common import discover_mods, base_parser, SETUP_DIR


ASSETS = ["icon.png", "LICENSE"]


def main():
    parser = base_parser("Copy shared assets (icon.png, LICENSE) into each mod's src/")
    args = parser.parse_args()

    print(f"\n  Asset deployment")
    print(f"  Overwrite: {args.overwrite}\n")

    count = 0
    for mod_dir in discover_mods():
        mod_name = os.path.basename(mod_dir)
        src_dir = os.path.join(mod_dir, "src")
        copied_any = False

        for asset in ASSETS:
            source = os.path.join(SETUP_DIR, asset)
            dest = os.path.join(src_dir, asset)

            if not os.path.exists(source):
                print(f"  WARNING: {asset} not found in Setup/")
                continue

            if os.path.exists(dest) and not args.overwrite:
                continue

            shutil.copy2(source, dest)
            copied_any = True

        if copied_any:
            print(f"  COPIED assets -> {mod_name}/src/")
            count += 1
        else:
            print(f"  SKIP (exists): {mod_name}")

    print(f"\nDone. {count} mods updated.\n")


if __name__ == "__main__":
    main()
