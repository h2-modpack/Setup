"""
Scaffold a new module repo from ModpackModuleTemplate.

Creates the GitHub repo, clones it into Submodules/, fills in the module
identity, wires git hooks, commits the filled files, pushes, and registers it
as a submodule.

Usage (run from the shell repo root):
  python Setup/scaffold/new_module.py --package-id LiveSplit --title "LiveSplit"
  python Setup/scaffold/new_module.py --package-id Gameplay_QoL --title "Gameplay QoL"

  --package-id Thunderstore package suffix and Lib/Framework module id.
  --title      Human display name.

Normally the script discovers pack identity from the shell repo:
  Pack ID      : coordinator src/main.lua PACK_ID
  Pack name    : coordinator src/main.lua WINDOW_TITLE
  Team         : coordinator thunderstore.toml package.namespace
  GitHub org   : shell repo origin remote

What will be created:
  GitHub repo : {org}/{team}-{package-id}      e.g. h2pack-speedrun/adamantSpeedrun-LiveSplit
  Local folder: Submodules/{team}-{package-id} e.g. Submodules/adamantSpeedrun-LiveSplit
  Thunderstore: {team}-{package-id}            e.g. adamantSpeedrun-LiveSplit

GitHub repo, local folder, Thunderstore ID, and plugin GUID are all the same
string so clone-then-deploy works without any manual renaming. The package id
is also used as the Lib/Framework module id.
"""

import os
import sys
import time
import argparse
import subprocess
import re
import tomllib
from register_submodules import update_core_deps
from setup_common import run


SETUP_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR       = os.path.dirname(SETUP_DIR)
SUBMODULES_DIR = os.path.join(ROOT_DIR, "Submodules")
TEMPLATE_REPO  = "h2-modpack/ModpackModuleTemplate"


def validate_package_id(value):
    """Thunderstore package suffix and Lib/Framework module id."""
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value or ""):
        raise ValueError("--package-id must start with a letter and contain only letters, numbers, and underscores")
    if value.startswith("_") or value.endswith("_") or "__" in value:
        raise ValueError("--package-id must not start/end with '_' or contain repeated underscores")


def validate_team(value):
    if not re.fullmatch(r"[A-Za-z0-9_]+", value or ""):
        raise ValueError("--team must contain only letters, numbers, and underscores")
    if value.startswith("_") or value.endswith("_"):
        raise ValueError("--team must not start or end with '_'")


def validate_org(value):
    if not re.fullmatch(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", value or ""):
        raise ValueError("--org must contain letters, numbers, and single hyphen separators only")


def validate_pack_id(value):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value or ""):
        raise ValueError("--pack-id must contain lowercase letters, numbers, and single hyphen separators only")


def validate_single_line(value, label):
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{label} must not be empty")
    if "\n" in normalized or "\r" in normalized:
        raise ValueError(f"{label} must be a single line")
    return normalized


def module_repo_name(team, package_id):
    return f"{team}-{package_id}"


def read_package(toml_path):
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)
    package = data.get("package", {})
    namespace = package.get("namespace")
    name = package.get("name")
    if not namespace or not name:
        raise RuntimeError(f"Missing package.namespace or package.name in {toml_path}")
    return package


def read_package_version(toml_path):
    """Read package.versionNumber from a Thunderstore config."""
    package = read_package(toml_path)
    version = package.get("versionNumber")
    if not version:
        raise RuntimeError(f"Missing package.versionNumber in {toml_path}")
    return version


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_lua_string(content, name, path):
    pattern = rf"\b{name}\s*=\s*['\"]([^'\"]+)['\"]"
    match = re.search(pattern, content)
    if not match:
        raise RuntimeError(f"Could not find {name} string in {path}")
    return match.group(1)


def discover_coordinator():
    hits = []
    for name in sorted(os.listdir(ROOT_DIR)):
        path = os.path.join(ROOT_DIR, name)
        toml_path = os.path.join(path, "thunderstore.toml")
        main_path = os.path.join(path, "src", "main.lua")
        if not os.path.isdir(path) or not os.path.isfile(toml_path) or not os.path.isfile(main_path):
            continue
        package = read_package(toml_path)
        package_name = package["name"]
        if package_name.endswith("_Modpack"):
            hits.append({
                "dir": name,
                "toml_path": toml_path,
                "main_path": main_path,
                "team": package["namespace"],
                "package": package_name,
            })

    if len(hits) != 1:
        found = ", ".join(hit["dir"] for hit in hits) or "none"
        raise RuntimeError(f"Expected exactly one coordinator repo in shell root, found: {found}")

    hit = hits[0]
    main = read_file(hit["main_path"])
    return {
        "pack_id": extract_lua_string(main, "PACK_ID", hit["main_path"]),
        "pack_name": extract_lua_string(main, "WINDOW_TITLE", hit["main_path"]),
        "team": hit["team"],
        "coordinator_package": hit["package"],
    }


def parse_github_remote(remote):
    match = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", remote.strip())
    if not match:
        return None, None
    return match.group(1), match.group(2)


def discover_github_shell():
    result = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None, os.path.basename(ROOT_DIR)
    org, repo = parse_github_remote(result.stdout)
    return org, repo or os.path.basename(ROOT_DIR)


# =============================================================================
# HELPERS
# =============================================================================

def replace_in_file(path, replacements):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for old, new in replacements.items():
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def replace_in_tree(root, replacements, suffixes=(".lua", ".md", ".toml")):
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if not filename.endswith(suffixes):
                continue
            replace_in_file(os.path.join(dirpath, filename), replacements)


def replace_dependency_version(path, dependency, version):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = rf'^({re.escape(dependency)}\s*=\s*)".*"$'
    replacement = rf'\1"{version}"'
    updated, count = re.subn(pattern, replacement, content, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"Could not find dependency {dependency} in {path}")

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(updated)


def remove_if_exists(path):
    if os.path.exists(path):
        os.remove(path)


def validate_current_lib_contract(local_path):
    """Fail fast if the external module template is missing required scaffold markers."""
    src_dir = os.path.join(local_path, "src")
    main_path = os.path.join(src_dir, "main.lua")
    data_path = os.path.join(src_dir, "mods", "data.lua")
    logic_path = os.path.join(src_dir, "logic.lua")
    if not os.path.exists(logic_path):
        logic_path = os.path.join(src_dir, "mods", "logic.lua")

    hits = []
    if not os.path.exists(main_path):
        hits.append("src/main.lua: missing module bootstrap file")
    if not os.path.exists(data_path):
        hits.append("src/mods/data.lua: missing data module file")
    if not os.path.exists(logic_path):
        hits.append("src/mods/logic.lua: missing logic module file")
    if hits:
        details = "\n  - ".join(hits)
        raise RuntimeError(
            "External module template does not match the scaffold script:\n"
            f"  - {details}\n"
            "Update h2-modpack/ModpackModuleTemplate before scaffolding this module."
        )

    main_content = read_file(main_path)
    data_content = read_file(data_path)
    logic_content = read_file(logic_path)

    hits = []
    main_markers = [
        "lib.createModule",
        "pluginGuid = PLUGIN_GUID",
        "local PLUGIN_GUID = _PLUGIN.guid",
        "module.data.define(data.buildStorage())",
        "module.ui.tab(ui.drawTab)",
        "module.ui.quickContent(ui.drawQuickContent)",
        "module.fallbackUi.attachGuiOnce(function(fallbackUi)",
        "rom.gui.add_imgui(fallbackUi.renderWindow)",
        "rom.gui.add_to_menu_bar(fallbackUi.addMenuBar)",
        "logic.attach(module)",
        "module.activate",
    ]
    data_markers = [
        "local data = {}",
        "function data.buildStorage()",
        "return data",
    ]
    logic_markers = [
        "local logic = {}",
        "function logic.bind(data)",
        "function logic.buildActions()",
        "function logic.buildPatchPlan(host, runtime, plan)",
        "function logic.registerHooks(moduleRef)",
        "moduleRef.hooks.wrap(",
        "runtime.data.read",
        "function logic.attach(moduleRef)",
        "moduleRef.actions.define(logic.buildActions())",
        "moduleRef.mutation.patch(logic.buildPatchPlan)",
        "return logic",
    ]
    stale_markers = [
        "TemplateModule_Internal",
        "TemplateModuleInternal",
        "TemplateModuleAnchor",
        "MODULE_ANCHOR",
        "moduleAnchor",
        "owner = moduleAnchor",
        "hookOwner",
        "WrapOwned",
        "OverrideOwned",
        "lib.tryCreateModule",
        "tryActivate",
        "lib.standaloneHost",
        "standaloneUiBridge",
        "hashGroupPlan",
        "buildHashGroupPlan",
        "registerPatchMutation",
        "function logic.registerHooks(host, store)",
        "store.read",
        "lib.hooks.",
        "host.hooks.wrap(",
        "storage = data.buildStorage()",
        "drawTab = ui.drawTab",
        "drawQuickContent = ui.drawQuickContent",
    ]
    for marker in main_markers:
        if marker not in main_content:
            hits.append(f"src/main.lua: missing current module bootstrap marker '{marker}'")
    for marker in data_markers:
        if marker not in data_content:
            hits.append(f"src/mods/data.lua: missing current data module marker '{marker}'")
    for marker in logic_markers:
        if marker not in logic_content:
            hits.append(f"{os.path.relpath(logic_path, local_path)}: missing current runtime-hook marker '{marker}'")
    for marker in stale_markers:
        if marker in main_content or marker in logic_content:
            hits.append(f"template still contains stale module pattern marker '{marker}'")

    if hits:
        details = "\n  - ".join(hits)
        raise RuntimeError(
            "External module template does not match the scaffold script:\n"
            f"  - {details}\n"
            "Update h2-modpack/ModpackModuleTemplate before scaffolding this module."
        )


def git(args, cwd=None):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)


MODULE_README = """\
# {title}

SCAFFOLD_TODO: Short description of what this module does.

Part of the [{pack_title} modpack]({shell_url}).

## What It Does

SCAFFOLD_TODO: Explain what this module lets players control.

## Gameplay Impact

SCAFFOLD_TODO: Explain how this module changes a run when enabled.

## How To Use

Install using r2modman. In game, open the {pack_title} menu and configure this module from the shared settings window.

## More Information

- [{pack_title} modpack]({shell_url})
"""


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Scaffold a new module repo from template")
    parser.add_argument("--package-id", required=True, help="Thunderstore package suffix and Lib/Framework module id")
    parser.add_argument("--title", required=True, help="Human display name (e.g. 'Gameplay QoL')")
    parser.add_argument("--pack-id", default=None, help="Override discovered pack id")
    parser.add_argument("--pack-name", default=None, help="Override discovered pack display name")
    parser.add_argument("--team", default=None, help="Override discovered pack Thunderstore team")
    parser.add_argument("--shared-team", default="adamant", help="Shared infrastructure team for Lib deps (default: adamant)")
    parser.add_argument("--org", default=None, help="Override discovered GitHub org")
    args = parser.parse_args()

    try:
        validate_package_id(args.package_id)
        module_title = validate_single_line(args.title, "--title")
        validate_team(args.shared_team)

        coordinator = discover_coordinator()
        discovered_org, shell_repo = discover_github_shell()

        pack_id = args.pack_id or coordinator["pack_id"]
        pack_name = args.pack_name or coordinator["pack_name"]
        team = args.team or coordinator["team"]
        org = args.org or discovered_org

        validate_pack_id(pack_id)
        pack_title = validate_single_line(pack_name, "--pack-name")
        validate_team(team)
        if not org:
            raise ValueError("--org is required when the shell repo origin is not a GitHub remote")
        validate_org(org)
    except (ValueError, RuntimeError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # GitHub repo, local folder, Thunderstore ID, and plugin GUID are all the same string.
    repo_name      = module_repo_name(team, args.package_id)      # adamantSpeedrun-LiveSplit
    website_url    = f"https://github.com/{org}/{repo_name}"
    local_path     = os.path.join(SUBMODULES_DIR, repo_name)
    submodule_rel  = f"Submodules/{repo_name}"
    shell_url      = f"https://github.com/{org}/{shell_repo}"
    lib_version    = read_package_version(os.path.join(ROOT_DIR, "adamant-ModpackLib", "thunderstore.toml"))

    print(f"""
  What will be created
  ---------------------------------------------
  Package ID     : {args.package_id}
  Display title  : {module_title}
  Pack ID        : {pack_id}
  Pack name      : {pack_title}
  Team           : {team}
  Shared deps    : {args.shared_team}-ModpackLib
  Thunderstore   : {repo_name}
  GitHub repo    : {org}/{repo_name}
  Local folder   : {submodule_rel}
  ---------------------------------------------""")

    answer = input("  Proceed? [y/N] ").strip().lower()
    if answer != "y":
        print("  Aborted.")
        sys.exit(0)

    if os.path.exists(local_path):
        print(f"\nERROR: {local_path} already exists.")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # Create GitHub repo from template
    # -------------------------------------------------------------------------
    print(f"\n>>> Creating repo {org}/{repo_name} from template...")
    run([
        "gh", "repo", "create", f"{org}/{repo_name}",
        "--public",
        "--template", TEMPLATE_REPO,
        "--description", module_title,
    ])

    # -------------------------------------------------------------------------
    # Clone into Submodules/
    # GitHub takes a few seconds to push the template branch after repo creation.
    # -------------------------------------------------------------------------
    print(f"\n>>> Cloning into {submodule_rel}...")
    clone_url = f"https://github.com/{org}/{repo_name}.git"
    for attempt in range(1, 6):
        result = subprocess.run(
            ["git", "clone", "--branch", "main", clone_url, local_path],
            capture_output=True,
        )
        if result.returncode == 0:
            break
        if attempt < 5:
            print(f"  Branch not ready yet, retrying in {attempt * 2}s... ({attempt}/5)")
            time.sleep(attempt * 2)
        else:
            print(result.stderr.decode())
            sys.exit(1)

    # -------------------------------------------------------------------------
    # Fill in module identity
    # -------------------------------------------------------------------------
    print("\n>>> Filling in module identity...")

    toml_path = os.path.join(local_path, "thunderstore.toml")
    replace_in_file(toml_path, {
        'namespace = "adamant"':              f'namespace = "{team}"',
        'name = "SCAFFOLD_TODO_ModName"':              f'name = "{args.package_id}"',
        '"SCAFFOLD_TODO: Short description of the mod"': f'"SCAFFOLD_TODO: description for {module_title}"',
        'https://github.com/h2-modpack/h2-modpack-SCAFFOLD_TODO_ModName': website_url,
        'readme = "./src/README.md"':         'readme = "./README.md"',
        'readme = "./THUNDERSTORE_README.md"': 'readme = "./README.md"',
    })
    if args.shared_team != "adamant":
        replace_in_file(toml_path, {
            "adamant-ModpackLib": f"{args.shared_team}-ModpackLib",
        })
    replace_dependency_version(toml_path, f"{args.shared_team}-ModpackLib", lib_version)

    readme_path = os.path.join(local_path, "README.md")
    with open(readme_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(MODULE_README.format(
            title=module_title,
            pack_title=pack_title,
            shell_url=shell_url,
        ))
    remove_if_exists(os.path.join(local_path, "THUNDERSTORE_README.md"))
    remove_if_exists(os.path.join(local_path, "src", "README.md"))

    # Fill PACK_ID in src/main.lua
    main_path = os.path.join(local_path, "src", "main.lua")
    if not os.path.exists(main_path):
        print(f"\nERROR: expected template file missing: {main_path}")
        sys.exit(1)

    identity_replacements = {
        "SCAFFOLD_TODO_ModuleId": args.package_id,
        "SCAFFOLD_TODO Module Name": module_title,
        "SCAFFOLD_TODO_SHORT": module_title,
        "SCAFFOLD_TODO tooltip": f"SCAFFOLD_TODO: tooltip for {module_title}",
    }
    replace_in_tree(os.path.join(local_path, "src"), identity_replacements, suffixes=(".lua",))

    replace_in_file(main_path, {
        'local PACK_ID = error("SCAFFOLD_TODO: set PACK_ID to your pack id")':
            f'local PACK_ID = "{pack_id}"',
    })
    validate_current_lib_contract(local_path)

    # -------------------------------------------------------------------------
    # Wire git hooks
    # -------------------------------------------------------------------------
    print("\n>>> Configuring git hooks...")
    githooks = os.path.join(local_path, ".githooks")
    if os.path.isdir(githooks):
        run(["git", "config", "core.hooksPath", ".githooks"], cwd=local_path)
    else:
        print("  (.githooks not found - skipping)")

    # -------------------------------------------------------------------------
    # Commit filled files and push
    # -------------------------------------------------------------------------
    print("\n>>> Committing filled identity files...")
    run(["git", "add", "-A"], cwd=local_path)

    result = git(["diff", "--cached", "--quiet"], cwd=local_path)
    if result.returncode == 0:
        print("  Nothing changed (template already filled?).")
    else:
        run(["git", "commit", "-m", f"init: {repo_name}"], cwd=local_path)
        run(["git", "push"], cwd=local_path)

    # -------------------------------------------------------------------------
    # Register as submodule in shell repo
    # -------------------------------------------------------------------------
    print(f"\n>>> Registering {submodule_rel} as submodule...")
    run([
        "git", "submodule", "add",
        "--branch", "main",
        clone_url, submodule_rel,
    ], cwd=ROOT_DIR)

    print("\n>>> Syncing coordinator module dependency block...")
    update_core_deps()

    print(f"""
==========================================================
  Done!

  Repo    : https://github.com/{org}/{repo_name}
  Local   : {local_path}

  Next steps:
    1. Edit src/main.lua and src/mods/*.lua - fill in definition fields and module behavior
    2. Review the synced coordinator thunderstore.toml dependency block
    3. python Setup/deploy/deploy_all.py --overwrite
    4. No secret update is needed if pack org secrets use All repositories access
==========================================================
""")


if __name__ == "__main__":
    main()
