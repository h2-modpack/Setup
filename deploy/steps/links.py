"""
Create profile symlinks for local deployment.
"""

import os

from .common import discover_packages, get_profile_path, get_toml_info


def create_link(target, link_path, overwrite):
    abs_target = os.path.abspath(target)
    abs_link = os.path.abspath(link_path)

    if not os.path.isdir(abs_target):
        return False

    if os.path.exists(abs_link) or os.path.lexists(abs_link):
        if not overwrite:
            print(f"  SKIP (exists): {abs_link}")
            return False
        try:
            os.remove(abs_link)
        except (OSError, PermissionError):
            os.rmdir(abs_link)

    os.makedirs(os.path.dirname(abs_link), exist_ok=True)
    os.symlink(abs_target, abs_link, target_is_directory=True)
    print(f"  LINKED: {abs_link}")
    return True


def deploy(overwrite, profile):
    profile_path = get_profile_path(profile)

    print(f"\n  Symlink deployment to profile: {profile}")
    print(f"  Overwrite: {overwrite}\n")

    count = 0
    for package_dir in discover_packages():
        namespace, name = get_toml_info(os.path.join(package_dir, "thunderstore.toml"))
        package_name = f"{namespace}-{name}"

        print(f"--- {package_name} ---")
        create_link(os.path.join(package_dir, "src"), os.path.join(profile_path, "plugins", package_name), overwrite)
        create_link(os.path.join(package_dir, "data"), os.path.join(profile_path, "plugins_data", package_name), overwrite)
        count += 1

    print(f"\nDone. {count} packages processed.\n")
    return count
