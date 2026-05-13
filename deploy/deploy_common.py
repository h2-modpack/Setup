"""
Shared utilities for deploy_* scripts.
"""

import os
import glob
import argparse
import platform
import tomllib


DEPLOY_DIR = os.path.dirname(os.path.abspath(__file__))
SETUP_DIR  = os.path.dirname(DEPLOY_DIR)
ROOT_DIR   = os.path.dirname(SETUP_DIR)
DEFAULT_PROFILE = "h2-dev"


def get_profile_path(profile_name):
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise RuntimeError("APPDATA is not set; cannot locate r2modman profile directory")
        return os.path.join(appdata, "r2modmanPlus-local", "HadesII", "profiles", profile_name, "ReturnOfModding")
    else:
        return os.path.expanduser(f"~/.config/r2modmanPlus-local/HadesII/profiles/{profile_name}/ReturnOfModding")


def get_toml_info(toml_path):
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)

    package = data.get("package", {})
    namespace = package.get("namespace")
    name = package.get("name")
    if not isinstance(namespace, str) or not namespace:
        raise RuntimeError(f"{toml_path} is missing package.namespace")
    if not isinstance(name, str) or not name:
        raise RuntimeError(f"{toml_path} is missing package.name")
    return namespace, name


def discover_mods():
    """Returns top-level dirs with thunderstore.toml, then Submodules/* with thunderstore.toml."""
    top_level = sorted(
        d for d in glob.glob(os.path.join(ROOT_DIR, "*"))
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, "thunderstore.toml"))
    )
    submodules = sorted(
        d for d in glob.glob(os.path.join(ROOT_DIR, "Submodules", "*"))
        if os.path.isfile(os.path.join(d, "thunderstore.toml"))
    )
    return top_level + submodules


def base_parser(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files/links (default: skip)")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help=f"r2modman profile name (default: {DEFAULT_PROFILE})")
    return parser
