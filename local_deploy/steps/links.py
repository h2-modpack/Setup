"""
Deploy package folders into an r2modman profile.
"""

import os
import platform
import shutil

from .common import discover_packages, get_profile_path, get_toml_info, is_wsl


def is_windows_mount_path(path):
    abs_path = os.path.abspath(path)
    parts = abs_path.split(os.sep)
    return len(parts) > 3 and parts[1] == "mnt" and len(parts[2]) == 1 and parts[2].isalpha()


def is_wsl_unc_path(path):
    normalized = str(path).replace("/", "\\").lower()
    if normalized.startswith("\\\\wsl$\\") or normalized.startswith("\\\\wsl.localhost\\"):
        return True
    abs_normalized = os.path.abspath(path).replace("/", "\\").lower()
    return abs_normalized.startswith("\\\\wsl$\\") or abs_normalized.startswith("\\\\wsl.localhost\\")


def remove_existing(path):
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)
        return
    if os.path.isdir(path):
        shutil.rmtree(path)


def resolve_link_mode(link_mode, profile_path, source_root=None):
    if link_mode != "auto":
        return link_mode
    if is_wsl() and is_windows_mount_path(profile_path):
        return "copy"
    if platform.system() == "Windows" and source_root and is_wsl_unc_path(source_root):
        return "copy"
    return "symlink"


def create_symlink(target, link_path, overwrite):
    abs_target = os.path.abspath(target)
    abs_link = os.path.abspath(link_path)

    if not os.path.isdir(abs_target):
        return False

    if os.path.exists(abs_link) or os.path.lexists(abs_link):
        if not overwrite:
            print(f"  SKIP (exists): {abs_link}")
            return False
        remove_existing(abs_link)

    os.makedirs(os.path.dirname(abs_link), exist_ok=True)
    os.symlink(abs_target, abs_link, target_is_directory=True)
    print(f"  LINKED: {abs_link}")
    return True


def copy_tree(target, link_path, overwrite):
    abs_target = os.path.abspath(target)
    abs_link = os.path.abspath(link_path)

    if not os.path.isdir(abs_target):
        return False

    if os.path.exists(abs_link) or os.path.lexists(abs_link):
        if not overwrite:
            print(f"  SKIP (exists): {abs_link}")
            return False
        remove_existing(abs_link)

    os.makedirs(os.path.dirname(abs_link), exist_ok=True)
    shutil.copytree(abs_target, abs_link)
    print(f"  COPIED: {abs_link}")
    return True


def deploy_path(target, link_path, overwrite, link_mode):
    if link_mode == "copy":
        return copy_tree(target, link_path, overwrite)
    return create_symlink(target, link_path, overwrite)


def deploy(overwrite, profile, profile_root=None, link_mode="auto"):
    profile_path = get_profile_path(profile, profile_root)
    resolved_mode = resolve_link_mode(link_mode, profile_path, os.getcwd())

    print(f"\n  Profile deployment to: {profile}")
    print(f"  Profile path: {profile_path}")
    print(f"  Link mode: {resolved_mode}")
    print(f"  Overwrite: {overwrite}\n")

    count = 0
    for package_dir in discover_packages():
        namespace, name = get_toml_info(os.path.join(package_dir, "thunderstore.toml"))
        package_name = f"{namespace}-{name}"

        print(f"--- {package_name} ---")
        deploy_path(os.path.join(package_dir, "src"), os.path.join(profile_path, "plugins", package_name), overwrite, resolved_mode)
        deploy_path(os.path.join(package_dir, "data"), os.path.join(profile_path, "plugins_data", package_name), overwrite, resolved_mode)
        count += 1

    print(f"\nDone. {count} packages processed.\n")
    return count
