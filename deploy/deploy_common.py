"""
Shared utilities for deploy_* scripts.
"""

import os
import glob
import argparse
import platform


DEPLOY_DIR = os.path.dirname(os.path.abspath(__file__))
SETUP_DIR  = os.path.dirname(DEPLOY_DIR)
ROOT_DIR   = os.path.dirname(SETUP_DIR)
DEFAULT_PROFILE = "h2-dev"


def get_profile_path(profile_name):
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        return os.path.join(appdata, "r2modmanPlus-local", "HadesII", "profiles", profile_name, "ReturnOfModding")
    else:
        return os.path.expanduser(f"~/.config/r2modmanPlus-local/HadesII/profiles/{profile_name}/ReturnOfModding")


def get_toml_info(toml_path):
    namespace, name = None, None
    with open(toml_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('namespace ='):
                namespace = line.split('=')[1].strip().strip('"\'')
            elif line.startswith('name ='):
                name = line.split('=')[1].strip().strip('"\'')
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
