"""
Scaffold a new module repo from h2-modpack-template.

Creates the GitHub repo, clones it into Submodules/, fills in the module
identity (namespace, name, pack-id, website URL), wires git hooks,
commits the filled files, pushes, and registers it as a submodule.

Usage (run from the shell repo root):
  python Setup/scaffold/new_module.py --name SkipPausingEncounters --pack-id speedrun --namespace adamant --org my-org

  --name      PascalCase module name   (e.g. SkipPausingEncounters)
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
from setup_common import run


SETUP_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR       = os.path.dirname(SETUP_DIR)
SUBMODULES_DIR = os.path.join(ROOT_DIR, "Submodules")
TEMPLATE_REPO  = "h2-modpack/h2-modpack-template"


def to_pascal(s):
    """Convert a kebab/snake/lower string to PascalCase. 'speedrun' -> 'Speedrun', 'my-pack' -> 'MyPack'."""
    return "".join(word.capitalize() for word in s.replace("-", " ").replace("_", " ").split())


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
    parser.add_argument("--name",      required=True,  help="PascalCase module name (e.g. SkipPausingEncounters)")
    parser.add_argument("--pack-id",   required=True,  help="Pack this module belongs to (e.g. speedrun)")
    parser.add_argument("--namespace", required=True,  help="Thunderstore namespace (e.g. 'adamant')")
    parser.add_argument("--org",       required=True,  help="GitHub org (e.g. 'h2-modpack')")
    parser.add_argument("--desc",      default=None,   help="Short description for Thunderstore and README (optional)")
    args = parser.parse_args()

    # GitHub repo, local folder, and Thunderstore ID are all the same string.
    repo_name      = f"{args.namespace}-{to_pascal(args.pack_id)}_{args.name}"         # adamant-Speedrun_SkipPausingEncounters
    website_url    = f"https://github.com/{args.org}/{repo_name}"
    local_path     = os.path.join(SUBMODULES_DIR, repo_name)
    submodule_rel  = f"Submodules/{repo_name}"
    pack_title     = " ".join(w.capitalize() for w in args.pack_id.replace("-", "_").split("_"))  # "run-director" -> "Run Director"
    shell_repo     = f"{args.pack_id}-modpack"
    shell_url      = f"https://github.com/{args.org}/{shell_repo}"

    print(f"""
  What will be created
  ─────────────────────────────────────────────
  Module name    : {args.name}
  Pack ID        : {args.pack_id}
  Thunderstore   : {repo_name}
  GitHub repo    : {args.org}/{repo_name}
  Local folder   : {submodule_rel}
  ─────────────────────────────────────────────""")

    answer = input("  Proceed? [y/N] ").strip().lower()
    if answer != "y":
        print("  Aborted.")
        sys.exit(0)

    if not args.name[0].isupper():
        print("ERROR: --name must be PascalCase (e.g. BossRush)")
        sys.exit(1)

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
        'name = "TODO_ModName"':              f'name = "{to_pascal(args.pack_id)}_{args.name}"',
        '"TODO: Short description of the mod"': f'"{args.desc or "TODO: description for " + args.name}"',
        'https://github.com/h2-modpack/h2-modpack-TODO_ModName': website_url,
    })

    readme_path = os.path.join(local_path, "README.md")
    if os.path.exists(readme_path):
        readme_replacements = {
            'TODO_ModName':   args.name,
            'TODO_PackTitle': pack_title,
            'TODO_ShellUrl':  shell_url,
        }
        if args.desc:
            readme_replacements['TODO: Short description of what this mod does.'] = args.desc
        replace_in_file(readme_path, readme_replacements)

    # Fill PACK_ID in src/main.lua
    main_path = os.path.join(local_path, "src", "main.lua")
    if not os.path.exists(main_path):
        print(f"\nERROR: expected template file missing: {main_path}")
        sys.exit(1)

    replace_in_file(main_path, {
        'local PACK_ID = error("TODO: set PACK_ID to your pack id")':
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
    run(["git", "add", "thunderstore.toml", "README.md", "src/main.lua"], cwd=local_path)

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

    print(f"""
==========================================================
  Done!

  Repo    : https://github.com/{args.org}/{repo_name}
  Local   : {local_path}

  Next steps:
    1. Edit src/main.lua — fill in definition fields and module logic
    2. python Setup/deploy/deploy_all.py --overwrite
==========================================================
""")


if __name__ == "__main__":
    main()
