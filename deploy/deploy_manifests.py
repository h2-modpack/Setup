"""
Generates manifest.json from thunderstore.toml for all mods.
Usage: python deploy_manifests.py [--overwrite] [--profile NAME]
"""

import os
from deploy_common import discover_mods, base_parser
from generate_manifest import write_manifest


def generate_manifest_for_mod(mod_dir, overwrite):
    """Generate src/manifest.json for one package if needed."""
    toml_path = os.path.join(mod_dir, "thunderstore.toml")
    output_path = os.path.join(mod_dir, "src", "manifest.json")
    mod_name = os.path.basename(mod_dir)

    if os.path.exists(output_path) and not overwrite:
        print(f"  SKIP (exists): {mod_name}/src/manifest.json")
        return False

    print(f"--- {mod_name} ---")
    write_manifest(toml_path, output_path)
    print(f"  Generated manifest: {output_path}")
    return True


def main():
    parser = base_parser("Generate manifest.json for all mods")
    args = parser.parse_args()

    print(f"\n  Manifest generation")
    print(f"  Overwrite: {args.overwrite}\n")

    count = 0
    for mod_dir in discover_mods():
        if generate_manifest_for_mod(mod_dir, args.overwrite):
            count += 1

    print(f"\nDone. {count} manifests generated.\n")


if __name__ == "__main__":
    main()
