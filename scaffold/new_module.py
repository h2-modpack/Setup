"""
Scaffold a new module repo from h2-modpack-template.

Creates the GitHub repo, clones it into Submodules/, fills in the module
identity (namespace, name, pack-id, website URL), wires git hooks,
commits the filled files, pushes, and registers it as a submodule.

Usage (run from the shell repo root):
  python Setup/scaffold/new_module.py --name SkipPausingEncounters --pack-id speedrun --namespace adamant --org my-org
  python Setup/scaffold/new_module.py --name GameplayQoL --title "Gameplay QoL" --pack-id speedrun --namespace adamant --org my-org

  --name      Package-safe PascalCase module id (e.g. SkipPausingEncounters, GameplayQoL)
  --title     Human display name       (optional; e.g. "Gameplay QoL")
  --pack-id   Pack this module belongs to (e.g. speedrun) - sets modpack field
  --namespace Thunderstore namespace   (e.g. adamant)
  --org       GitHub org               (e.g. h2-modpack)

What will be created:
  GitHub repo : {org}/{ns}-{PackId}_{name}      e.g. h2pack-speedrun/adamant-Speedrun_SkipPausingEncounters
  Local folder: Submodules/{ns}-{PackId}_{name} e.g. Submodules/adamant-Speedrun_SkipPausingEncounters
  Thunderstore: {ns}-{PackId}_{name}             e.g. adamant-Speedrun_SkipPausingEncounters

GitHub repo, local folder, and Thunderstore ID are all the same string so
clone-then-deploy works without any manual renaming.
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
TEMPLATE_REPO  = "h2-modpack/h2-modpack-template"
KNOWN_ACRONYMS = ("QoL", "LrT", "RTA", "IGT")


def to_pascal(s):
    """Convert a kebab/snake/lower string to PascalCase. 'speedrun' -> 'Speedrun', 'my-pack' -> 'MyPack'."""
    return "".join(word.capitalize() for word in s.replace("-", " ").replace("_", " ").split())


def pascal_to_title(s):
    """Convert PascalCase / acronym-ish names to a readable title."""
    tokens = []
    index = 0
    while index < len(s):
        acronym = next((item for item in KNOWN_ACRONYMS if s.startswith(item, index)), None)
        if acronym:
            tokens.append(acronym)
            index += len(acronym)
            continue

        match = re.match(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|$)|[0-9]+", s[index:])
        if match:
            tokens.append(match.group(0))
            index += len(match.group(0))
            continue

        tokens.append(s[index])
        index += 1

    return " ".join(tokens).strip() or s


def validate_module_name(name):
    """Thunderstore package component / repo suffix: no spaces, PascalCase-ish."""
    if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", name or ""):
        raise ValueError("--name must be package-safe PascalCase without spaces (e.g. BossRush, GameplayQoL)")


def normalize_title(title):
    if title is None:
        return None
    normalized = title.strip()
    if not normalized:
        raise ValueError("--title must not be empty when provided")
    if "\n" in normalized or "\r" in normalized:
        raise ValueError("--title must be a single line")
    return normalized


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
            "Update h2-modpack/h2-modpack-template before scaffolding this module."
        )

    with open(main_path, "r", encoding="utf-8") as f:
        main_content = f.read()
    with open(data_path, "r", encoding="utf-8") as f:
        data_content = f.read()
    with open(logic_path, "r", encoding="utf-8") as f:
        logic_content = f.read()

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
            "Update h2-modpack/h2-modpack-template before scaffolding this module."
        )


def git(args, cwd=None):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)


def read_package_version(toml_path):
    """Read package.versionNumber from a Thunderstore config."""
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)
    version = data.get("package", {}).get("versionNumber")
    if not version:
        raise RuntimeError(f"Missing package.versionNumber in {toml_path}")
    return version


MODULE_README = """\
# {title}

{description}

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
    parser.add_argument("--name",      required=True,  help="PascalCase module name (e.g. SkipPausingEncounters)")
    parser.add_argument("--title",     default=None,   help="Human display name (optional; e.g. 'Gameplay QoL')")
    parser.add_argument("--pack-id",   required=True,  help="Pack this module belongs to (e.g. speedrun)")
    parser.add_argument("--namespace", required=True,  help="Thunderstore namespace (e.g. 'adamant')")
    parser.add_argument("--org",       required=True,  help="GitHub org (e.g. 'h2-modpack')")
    parser.add_argument("--desc",      default=None,   help="Short description for Thunderstore and README (optional)")
    args = parser.parse_args()

    try:
        validate_module_name(args.name)
        module_title = normalize_title(args.title) or pascal_to_title(args.name)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # GitHub repo, local folder, and Thunderstore ID are all the same string.
    repo_name      = f"{args.namespace}-{to_pascal(args.pack_id)}_{args.name}"         # adamant-Speedrun_SkipPausingEncounters
    website_url    = f"https://github.com/{args.org}/{repo_name}"
    local_path     = os.path.join(SUBMODULES_DIR, repo_name)
    submodule_rel  = f"Submodules/{repo_name}"
    pack_pascal    = to_pascal(args.pack_id)
    pack_title     = " ".join(w.capitalize() for w in args.pack_id.replace("-", "_").split("_"))  # "run-director" -> "Run Director"
    shell_repo     = f"{args.pack_id}-modpack"
    shell_url      = f"https://github.com/{args.org}/{shell_repo}"
    lib_version    = read_package_version(os.path.join(ROOT_DIR, "adamant-ModpackLib", "thunderstore.toml"))

    print(f"""
  What will be created
  ---------------------------------------------
  Module ID      : {args.name}
  Display title  : {module_title}
  Pack ID        : {args.pack_id}
  Thunderstore   : {repo_name}
  GitHub repo    : {args.org}/{repo_name}
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
    print(f"\n>>> Creating repo {args.org}/{repo_name} from template...")
    run([
        "gh", "repo", "create", f"{args.org}/{repo_name}",
        "--public",
        "--template", TEMPLATE_REPO,
        "--description", args.desc or args.name,
    ])

    # -------------------------------------------------------------------------
    # Clone into Submodules/
    # GitHub takes a few seconds to push the template branch after repo creation.
    # -------------------------------------------------------------------------
    print(f"\n>>> Cloning into {submodule_rel}...")
    clone_url = f"https://github.com/{args.org}/{repo_name}.git"
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
        'namespace = "adamant"':              f'namespace = "{args.namespace}"',
        'name = "SCAFFOLD_TODO_ModName"':              f'name = "{pack_pascal}_{args.name}"',
        '"SCAFFOLD_TODO: Short description of the mod"': f'"{args.desc or "SCAFFOLD_TODO: description for " + args.name}"',
        'https://github.com/h2-modpack/h2-modpack-SCAFFOLD_TODO_ModName': website_url,
        'readme = "./src/README.md"':         'readme = "./README.md"',
        'readme = "./THUNDERSTORE_README.md"': 'readme = "./README.md"',
    })
    replace_dependency_version(toml_path, "adamant-ModpackLib", lib_version)

    readme_path = os.path.join(local_path, "README.md")
    with open(readme_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(MODULE_README.format(
            title=module_title,
            description=args.desc or "SCAFFOLD_TODO: Short description of what this module does.",
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
        "SCAFFOLD_TODO_ModuleId": args.name,
        "SCAFFOLD_TODO Module Name": module_title,
        "SCAFFOLD_TODO_SHORT": args.name,
        "SCAFFOLD_TODO tooltip": args.desc or f"SCAFFOLD_TODO: tooltip for {module_title}",
    }
    replace_in_tree(os.path.join(local_path, "src"), identity_replacements, suffixes=(".lua",))

    replace_in_file(main_path, {
        'local PACK_ID = error("SCAFFOLD_TODO: set PACK_ID to your pack id")':
            f'local PACK_ID = "{args.pack_id}"',
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

    print("\n>>> Syncing Core module dependency block...")
    update_core_deps()

    print(f"""
==========================================================
  Done!

  Repo    : https://github.com/{args.org}/{repo_name}
  Local   : {local_path}

  Next steps:
    1. Edit src/main.lua and src/mods/*.lua - fill in definition fields and module behavior
    2. Review the synced Core thunderstore.toml dependency block
    3. python Setup/deploy/deploy_all.py --overwrite
    4. No secret update is needed if pack org secrets use All repositories access
==========================================================
""")


if __name__ == "__main__":
    main()
