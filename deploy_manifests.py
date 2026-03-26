"""
Generates manifest.json from thunderstore.toml for all mods.
Usage: python deploy_manifests.py [--overwrite] [--profile NAME]
"""

import os
import sys
import subprocess
from deploy_common import discover_mods, base_parser, SETUP_DIR


def main():
    parser = base_parser("Generate manifest.json for all mods")
    args = parser.parse_args()
    gen_script = os.path.join(SETUP_DIR, "generate_manifest.py")

    print(f"\n  Manifest generation")
    print(f"  Overwrite: {args.overwrite}\n")

    count = 0
    for mod_dir in discover_mods():
        toml_path = os.path.join(mod_dir, "thunderstore.toml")
        output_path = os.path.join(mod_dir, "src", "manifest.json")
        mod_name = os.path.basename(mod_dir)

        if os.path.exists(output_path) and not args.overwrite:
            print(f"  SKIP (exists): {mod_name}/src/manifest.json")
            continue

        print(f"--- {mod_name} ---")
        subprocess.run([sys.executable, gen_script, toml_path, output_path], check=True)
        count += 1

    print(f"\nDone. {count} manifests generated.\n")


if __name__ == "__main__":
    main()
