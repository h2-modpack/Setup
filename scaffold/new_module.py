"""
Scaffold a new module repo from h2-modpack-template.

Creates the GitHub repo, clones it into Submodules/, fills in the module
identity (namespace, name, pack-id, website URL), wires git hooks,
commits the filled files, pushes, and registers it as a submodule.

Usage (run from the shell repo root):
  python Setup/new_module.py --name SkipPausingEncounters --pack-id speedrun

  --name      PascalCase module name   (e.g. SkipPausingEncounters)
  --pack-id   Pack this module belongs to (e.g. speedrun) — sets modpack field
  --namespace Thunderstore namespace   (default: adamant)
  --org       GitHub org               (default: h2-modpack)

What will be created:
  GitHub repo : {org}/{org}-{name}          e.g. h2-modpack/h2-modpack-SkipPausingEncounters
  Local folder: Submodules/{ns}-{name}      e.g. Submodules/adamant-SkipPausingEncounters
  Thunderstore: {ns}-{name}                 e.g. adamant-SkipPausingEncounters
"""

import os
import sys
import argparse
import subprocess
from setup_common import run, rmtree


SETUP_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR       = os.path.dirname(SETUP_DIR)
SUBMODULES_DIR = os.path.join(ROOT_DIR, "Submodules")
TEMPLATE_REPO  = "h2-modpack/h2-modpack-template"


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


def git(args, cwd=None):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Scaffold a new module repo from template")
    parser.add_argument("--name",      required=True,           help="PascalCase module name (e.g. SkipPausingEncounters)")
    parser.add_argument("--pack-id",   required=True,           help="Pack this module belongs to (e.g. speedrun)")
    parser.add_argument("--namespace", default="adamant",       help="Thunderstore namespace (default: adamant)")
    parser.add_argument("--org",       default="h2-modpack",    help="GitHub org (default: h2-modpack)")
    args = parser.parse_args()

    module_id   = f"{args.namespace}-{args.name}"           # adamant-SkipPausingEncounters
    repo_name   = f"{args.org}-{args.name}"                 # h2-modpack-SkipPausingEncounters
    website_url = f"https://github.com/{args.org}/{repo_name}"
    local_path  = os.path.join(SUBMODULES_DIR, module_id)
    submodule_rel = f"Submodules/{module_id}"

    print(f"""
  What will be created
  ─────────────────────────────────────────────
  Module name    : {args.name}
  Pack ID        : {args.pack_id}
  Thunderstore   : {module_id}
  GitHub repo    : {args.org}/{repo_name}
  Local folder   : {submodule_rel}
  ─────────────────────────────────────────────""")

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
        "--description", f"{args.name} module",
    ])

    # -------------------------------------------------------------------------
    # Clone into Submodules/
    # -------------------------------------------------------------------------
    print(f"\n>>> Cloning into {submodule_rel}...")
    clone_url = f"https://github.com/{args.org}/{repo_name}.git"
    run(["git", "clone", "--branch", "main", clone_url, local_path])

    # -------------------------------------------------------------------------
    # Fill in module identity
    # -------------------------------------------------------------------------
    print("\n>>> Filling in module identity...")

    toml_path = os.path.join(local_path, "thunderstore.toml")
    replace_in_file(toml_path, {
        'namespace = "adamant"':              f'namespace = "{args.namespace}"',
        'name = "TODO_ModName"':              f'name = "{args.name}"',
        '"TODO: Short description of the mod"': f'"TODO: description for {args.name}"',
        'https://github.com/h2-modpack/h2-modpack-TODO_ModName': website_url,
    })

    # Set PACK_ID in main.lua (replace the error() placeholder with the actual value)
    main_lua = os.path.join(local_path, "src", "main.lua")
    replace_in_file(main_lua, {
        'local PACK_ID     = error("FILL: set PACK_ID to your pack id, e.g. \\"h2-modpack\\"")':
            f'local PACK_ID = "{args.pack_id}"',
    })

    # -------------------------------------------------------------------------
    # Wire git hooks
    # -------------------------------------------------------------------------
    print("\n>>> Configuring git hooks...")
    githooks = os.path.join(local_path, ".githooks")
    if os.path.isdir(githooks):
        run(["git", "config", "core.hooksPath", ".githooks"], cwd=local_path)
    else:
        print("  (.githooks not found — skipping)")

    # -------------------------------------------------------------------------
    # Commit filled files and push
    # -------------------------------------------------------------------------
    print("\n>>> Committing filled identity files...")
    run(["git", "add", "thunderstore.toml", "src/main.lua"], cwd=local_path)

    result = git(["diff", "--cached", "--quiet"], cwd=local_path)
    if result.returncode == 0:
        print("  Nothing changed (template already filled?).")
    else:
        run(["git", "commit", "-m", f"init: {module_id}"], cwd=local_path)
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

    print(f"""
==========================================================
  Done!

  Repo    : https://github.com/{args.org}/{repo_name}
  Local   : {local_path}

  Next steps:
    1. Edit src/main.lua — fill in apply(), revert(), definition fields
    2. python Setup/deploy_all.py --overwrite
==========================================================
""")


if __name__ == "__main__":
    main()
