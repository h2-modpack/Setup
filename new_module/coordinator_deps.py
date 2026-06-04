"""
Sync the coordinator module's managed Thunderstore dependency block.
"""

import os
import re
import tomllib


TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(TOOLS_DIR)
SUBMODULES_DIR = os.path.join(ROOT_DIR, "Submodules")

MARKER_START = "# -- submodules-start --"
MARKER_END = "# -- submodules-end --"


def find_coordinator_toml():
    """Find the coordinator module's thunderstore.toml in root-level folders."""
    for entry in os.scandir(ROOT_DIR):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        toml_path = os.path.join(entry.path, "thunderstore.toml")
        if not os.path.exists(toml_path):
            continue
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
        name = data.get("package", {}).get("name", "")
        if name.endswith("_Modpack"):
            return toml_path
    return None


def submodule_version(name):
    """Read versionNumber from a submodule's thunderstore.toml, default 1.0.0."""
    toml_path = os.path.join(SUBMODULES_DIR, name, "thunderstore.toml")
    if not os.path.exists(toml_path):
        return "1.0.0"
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)
    return data.get("package", {}).get("versionNumber", "1.0.0")


def submodule_package_id(name):
    """Read {namespace}-{name} from a submodule's thunderstore.toml, fall back to folder name."""
    toml_path = os.path.join(SUBMODULES_DIR, name, "thunderstore.toml")
    if not os.path.exists(toml_path):
        return name
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)
    pkg = data.get("package", {})
    namespace = pkg.get("namespace", "")
    package_name = pkg.get("name", "")
    if namespace and package_name:
        return f"{namespace}-{package_name}"
    return name


def current_submodule_names():
    """Return sorted list of submodule folder names in Submodules/."""
    names = []
    for entry in sorted(os.scandir(SUBMODULES_DIR), key=lambda e: e.name):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if not os.path.exists(os.path.join(entry.path, ".git")):
            continue
        names.append(entry.name)
    return names


def update_coordinator_deps():
    """Sync the managed submodule block in the coordinator thunderstore.toml."""
    print("Syncing coordinator module dependencies...")
    print("  Detecting coordinator module: scanning root-level folders for a thunderstore.toml")
    print("  whose package name ends in '_Modpack'...")

    coordinator_toml = find_coordinator_toml()
    if not coordinator_toml:
        print("  WARN  No coordinator module found, skipping dep sync.")
        return

    print(f"  found   {os.path.relpath(coordinator_toml, ROOT_DIR)}")
    print(f"  Replacing managed block between '{MARKER_START}' and '{MARKER_END}'")
    print("  (infrastructure deps above the markers are left untouched)")

    names = current_submodule_names()
    lines = [f'{submodule_package_id(name)} = "{submodule_version(name)}"' for name in names]
    block = MARKER_START + "\n" + "\n".join(lines) + "\n" + MARKER_END

    text = open(coordinator_toml, encoding="utf-8").read()

    if MARKER_START in text:
        pattern = re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END)
        new_text = re.sub(pattern, block, text, flags=re.DOTALL)
    else:
        dep_header = "[package.dependencies]"
        if dep_header not in text:
            print("  WARN  No [package.dependencies] section in coordinator toml, skipping dep sync.")
            return
        match = re.search(r"(\[package\.dependencies\].*?)(\n\[)", text, re.DOTALL)
        if match:
            new_text = text[:match.start(2)] + "\n" + block + "\n" + text[match.start(2):]
        else:
            new_text = text.rstrip() + "\n" + block + "\n"

    open(coordinator_toml, "w", encoding="utf-8").write(new_text)
    print(f"  synced  coordinator deps ({len(names)} submodules)  ->  {os.path.relpath(coordinator_toml, ROOT_DIR)}")
    print()
    print("  NOTE: Run `python ModpackTools/local_deploy/deploy_all.py --overwrite` to deploy changes to the game.")
