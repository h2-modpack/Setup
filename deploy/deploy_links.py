"""
Creates symlinks for all mods (src -> plugins, data -> plugins_data).
Usage: python deploy_links.py [--overwrite] [--profile NAME]
"""

import os
import sys
from deploy_common import discover_mods, get_toml_info, get_profile_path, base_parser


def create_link(target, link_path, overwrite):
    abs_target = os.path.abspath(target)
    abs_link = os.path.abspath(link_path)

    if not os.path.isdir(abs_target):
        return

    if os.path.exists(abs_link) or os.path.lexists(abs_link):
        if not overwrite:
            print(f"  SKIP (exists): {abs_link}")
            return
        # Windows requires os.rmdir for directory symlinks, Unix uses os.remove
        try:
            os.remove(abs_link)
        except (OSError, PermissionError):
            os.rmdir(abs_link)

    os.makedirs(os.path.dirname(abs_link), exist_ok=True)
    os.symlink(abs_target, abs_link, target_is_directory=True)
    print(f"  LINKED: {abs_link}")


def main():
    parser = base_parser("Create symlinks for all mods")
    args = parser.parse_args()
    profile_path = get_profile_path(args.profile)

    print(f"\n  Symlink deployment to profile: {args.profile}")
    print(f"  Overwrite: {args.overwrite}\n")

    count = 0
    for mod_dir in discover_mods():
        ns, name = get_toml_info(os.path.join(mod_dir, "thunderstore.toml"))
        if not ns or not name:
            print(f"SKIP: {mod_dir}")
            continue

        mod_name = f"{ns}-{name}"
        print(f"--- {mod_name} ---")
        create_link(os.path.join(mod_dir, "src"), os.path.join(profile_path, "plugins", mod_name), args.overwrite)
        create_link(os.path.join(mod_dir, "data"), os.path.join(profile_path, "plugins_data", mod_name), args.overwrite)
        count += 1

    print(f"\nDone. {count} mods processed.\n")


if __name__ == "__main__":
    main()
