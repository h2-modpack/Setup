"""
Scaffolds a new modpack shell repo with Lib, Framework, and a coordinator.
Creates the coordinator GitHub repo automatically via the gh CLI.

Clone Setup next to where you want the new pack, then run:

  git clone https://github.com/h2-modpack/Setup.git
  python Setup/scaffold/new_pack.py --pack-id "speedrun" --namespace mynamespace --org my-org

The shell repo is created as a sibling of the Setup folder:
  ../speedrun-modpack/

The standalone Setup clone is deleted at the end — it re-enters as a submodule.

Naming convention:
  --pack-id should be a single lowercase word (e.g. "speedrun", "hades", "pvp").
  Multi-word pack IDs work but produce longer coordinator names.

  Given --pack-id "speedrun" --namespace "adamant":
    Shell repo:        speedrun-modpack
    Coordinator ID:    adamant-Speedrun_Core
    Coordinator repo:  adamant-Speedrun_Core
    Lib folder:        adamant-ModpackLib
    Framework folder:  adamant-ModpackFramework

Optional:
  [--title "Speedrun Modpack"]  default: title-case of pack-id

After running:
  cd ../speedrun-modpack
  python Setup/deploy/deploy_all.py --overwrite
"""

import os
import sys
import shutil
import argparse
import json
import tomllib
from setup_common import rmtree, fill, write, run


SETUP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR  = os.path.dirname(SETUP_DIR)

LIB_URL       = "https://github.com/h2-modpack/adamant-ModpackLib.git"
FRAMEWORK_URL = "https://github.com/h2-modpack/adamant-ModpackFramework.git"
SETUP_URL     = "https://github.com/h2-modpack/Setup.git"


# =============================================================================
# TEMPLATES
# =============================================================================
# Use {{PLACEHOLDER}} markers — simple .replace(), no f-string conflicts with Lua.

CONFIG_LUA = """\
---@meta {{NAMESPACE}}-config-{{NAME}}
return {
    ModEnabled  = true,
    DebugMode   = false,

    Profiles =
    {
        { Name = "", Hash = "", Tooltip = "" },
        { Name = "", Hash = "", Tooltip = "" },
        { Name = "", Hash = "", Tooltip = "" },
        { Name = "", Hash = "", Tooltip = "" },
        { Name = "", Hash = "", Tooltip = "" },
        { Name = "", Hash = "", Tooltip = "" },
        { Name = "", Hash = "", Tooltip = "" },
        { Name = "", Hash = "", Tooltip = "" },
        { Name = "", Hash = "", Tooltip = "" },
        { Name = "", Hash = "", Tooltip = "" },
    },
}
"""

THUNDERSTORE_TOML = """\
[config]
schemaVersion = "0.0.1"


[package]
namespace = "{{NAMESPACE}}"
name = "{{NAME}}"
versionNumber = "1.0.0"
description = "{{WINDOW_TITLE}} modpack coordinator."
websiteUrl = "https://github.com/{{ORG}}/{{COORD_REPO}}"
containsNsfwContent = false

[package.dependencies]
Hell2Modding-Hell2Modding = "1.0.78"
LuaENVY-ENVY = "1.2.0"
SGG_Modding-Chalk = "2.1.1"
SGG_Modding-ReLoad = "1.0.2"
SGG_Modding-ModUtil = "4.0.1"
adamant-ModpackLib = "{{LIB_VERSION}}"
adamant-ModpackFramework = "{{FRAMEWORK_VERSION}}"

# -- submodules-start --

# -- submodules-end --

[build]
icon = "./icon.png"
readme = "./README.md"
outdir = "./build"

[[build.copy]]
source = "./CHANGELOG.md"
target = "./CHANGELOG.md"

[[build.copy]]
source = "./LICENSE"
target = "./LICENSE"

[[build.copy]]
source = "./src"
target = "./plugins"


[publish]
repository = "https://thunderstore.io"
communities = [ "hades-ii", ]

[publish.categories]
hades-ii = [ "mods", ]
"""

CHANGELOG_MD = """\
# Changelog

## [Unreleased]

## [1.0.0]

- Initial release
"""

# =============================================================================
# MAIN
# =============================================================================

def pack_id_to_title(pack_id):
    """'run-director' -> 'Run Director'"""
    return " ".join(w.capitalize() for w in pack_id.replace("_", "-").split("-"))


def pack_id_to_pascal(pack_id):
    """'speedrun' -> 'Speedrun',  'my-pack' -> 'MyPack'"""
    return "".join(w.capitalize() for w in pack_id.replace("-", "_").split("_"))


def pack_id_to_name(pack_id):
    """'speedrun' -> 'Speedrun_Core'"""
    return pack_id_to_pascal(pack_id) + "_Core"


def read_package_version(toml_path):
    """Read package.versionNumber from a Thunderstore config."""
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)
    version = data.get("package", {}).get("versionNumber")
    if not version:
        raise RuntimeError(f"Missing package.versionNumber in {toml_path}")
    return version


def main():
    parser = argparse.ArgumentParser(description="Scaffold a new modpack shell repo")
    parser.add_argument("--pack-id",   required=True,  help="Pack ID used in Framework.init — single word preferred (e.g. 'speedrun')")
    parser.add_argument("--namespace", required=True,  help="Thunderstore namespace (e.g. 'adamant')")
    parser.add_argument("--title",     default=None,   help="Window title (default: title-case of pack-id)")
    parser.add_argument("--org",       required=True,        help="GitHub org (e.g. 'my-org')")
    args = parser.parse_args()

    title  = args.title or pack_id_to_title(args.pack_id)
    name   = pack_id_to_name(args.pack_id)
    output = os.path.join(ROOT_DIR, f"{args.pack_id}-modpack")

    shell_repo       = f"{args.pack_id}-modpack"
    shell_url        = f"https://github.com/{args.org}/{shell_repo}.git"
    coordinator_id   = f"{args.namespace}-{name}"                          # adamant-Speedrun_Core
    coordinator_repo = coordinator_id                                       # GitHub repo name = Thunderstore ID = local folder
    coordinator_url  = f"https://github.com/{args.org}/{coordinator_repo}.git"

    print(f"""
  What will be created
  ─────────────────────────────────────────────
  Window title   : {title}
  Pack ID        : {args.pack_id}
  Local output   : {output}

  GitHub repos (will be created under {args.org}/)
    Shell        : {shell_repo}
    Coordinator  : {coordinator_repo}  (github.com/{args.org}/{coordinator_repo})

  Submodule folders
    Lib          : adamant-ModpackLib
    Framework    : adamant-ModpackFramework
    Coordinator  : {coordinator_id}

  Thunderstore IDs
    Coordinator  : {coordinator_id}  (namespace={args.namespace}, name={name})
  ─────────────────────────────────────────────""")

    answer = input("  Proceed? [y/N] ").strip().lower()
    if answer != "y":
        print("  Aborted.")
        sys.exit(0)

    if os.path.exists(output):
        print(f"\nERROR: {output} already exists.")
        sys.exit(1)

    os.makedirs(output)

    # -------------------------------------------------------------------------
    # Shell repo — create on GitHub, init locally, set remote
    # -------------------------------------------------------------------------
    print(f">>> Creating shell repo {args.org}/{shell_repo}...")
    run([
        "gh", "repo", "create", f"{args.org}/{shell_repo}",
        "--public",
        "--description", f"{title} modpack",
    ])

    print("\n>>> Initialising git repo...")
    run(["git", "init", "-b", "main"],                    cwd=output)
    run(["git", "remote", "add", "origin", shell_url],    cwd=output)

    # -------------------------------------------------------------------------
    # Lib and Framework submodules
    # -------------------------------------------------------------------------
    print("\n>>> Adding Lib submodule...")
    run(["git", "submodule", "add", "--branch", "main", LIB_URL, "adamant-ModpackLib"], cwd=output)

    print("\n>>> Adding Framework submodule...")
    run(["git", "submodule", "add", "--branch", "main", FRAMEWORK_URL, "adamant-ModpackFramework"], cwd=output)

    lib_version = read_package_version(os.path.join(output, "adamant-ModpackLib", "thunderstore.toml"))
    framework_version = read_package_version(os.path.join(output, "adamant-ModpackFramework", "thunderstore.toml"))

    # -------------------------------------------------------------------------
    # Coordinator — generate files, push to new GitHub repo, then add as submodule
    # -------------------------------------------------------------------------
    coord_dir = os.path.join(output, coordinator_id)

    print(f"\n>>> Creating coordinator repo {args.org}/{coordinator_repo}...")
    run([
        "gh", "repo", "create", f"{args.org}/{coordinator_repo}",
        "--public",
        "--description", f"{title} modpack coordinator",
    ])

    # Generate coordinator files into a local git repo and push first,
    # so the remote has a commit before we add it as a submodule.
    print(f"\n>>> Initialising coordinator and pushing initial commit...")
    subs = dict(
        COORD_ID     = coordinator_id,
        PACK_ID      = args.pack_id,
        PACK_PASCAL  = pack_id_to_pascal(args.pack_id),
        WINDOW_TITLE = title,
        NAMESPACE    = args.namespace,
        NAME         = name,
        ORG          = args.org,
        SHELL_REPO   = shell_repo,
        COORD_REPO   = coordinator_repo,
        LIB_VERSION  = lib_version,
        FRAMEWORK_VERSION = framework_version,
    )
    write(os.path.join(coord_dir, "src", "config.lua"),   fill(CONFIG_LUA,        **subs))
    write(os.path.join(coord_dir, "thunderstore.toml"),   fill(THUNDERSTORE_TOML, **subs))
    write(os.path.join(coord_dir, "CHANGELOG.md"),        CHANGELOG_MD)

    templates_dir = os.path.join(SETUP_DIR, "templates", "coordinator")
    for dirpath, _, filenames in os.walk(templates_dir):
        for filename in filenames:
            src = os.path.join(dirpath, filename)
            rel = os.path.relpath(src, templates_dir)
            dst = os.path.join(coord_dir, rel)
            with open(src, "r", encoding="utf-8") as f:
                write(dst, fill(f.read(), **subs))
            if os.path.basename(src) == "pre-commit":
                os.chmod(dst, 0o755)

    # Shared assets from Setup/ root
    shutil.copy2(os.path.join(SETUP_DIR, "icon.png"), os.path.join(coord_dir, "icon.png"))
    shutil.copy2(os.path.join(SETUP_DIR, "LICENSE"),  os.path.join(coord_dir, "LICENSE"))

    manifest = {
        "namespace":      args.namespace,
        "name":           name,
        "description":    f"{title} modpack coordinator.",
        "version_number": "1.0.0",
        "dependencies": [
            "Hell2Modding-Hell2Modding-1.0.78",
            "LuaENVY-ENVY-1.2.0",
            "SGG_Modding-Chalk-2.1.1",
            "SGG_Modding-ReLoad-1.0.2",
            "SGG_Modding-ModUtil-4.0.1",
            f"adamant-ModpackLib-{lib_version}",
            f"adamant-ModpackFramework-{framework_version}",
        ],
        "website_url": f"https://github.com/{args.org}/{coordinator_repo}",
        "FullName": coordinator_id,
    }
    write(os.path.join(coord_dir, "src", "manifest.json"), json.dumps(manifest, indent=2) + "\n")

    run(["git", "init", "-b", "main"],                              cwd=coord_dir)
    run(["git", "remote", "add", "origin", coordinator_url],        cwd=coord_dir)
    run(["git", "add", "."],                                         cwd=coord_dir)
    run(["git", "commit", "-m", "Initial commit"],                   cwd=coord_dir)
    run(["git", "push", "-u", "origin", "main"],                     cwd=coord_dir)

    # Remove the local dir so git submodule add can clone it cleanly.
    rmtree(coord_dir)

    print(f"\n>>> Adding coordinator as submodule...")
    run(["git", "submodule", "add", "--branch", "main", coordinator_url, coordinator_id], cwd=output)

    # -------------------------------------------------------------------------
    # Submodules/ placeholder
    # -------------------------------------------------------------------------
    write(os.path.join(output, "Submodules", ".gitkeep"), "")

    # -------------------------------------------------------------------------
    # Shell repo template files (.gitignore, workflows, README, etc.)
    # -------------------------------------------------------------------------
    shell_templates_dir = os.path.join(SETUP_DIR, "templates", "shell")
    if os.path.isdir(shell_templates_dir):
        print("\n>>> Copying shell templates...")
        for dirpath, _, filenames in os.walk(shell_templates_dir):
            for filename in filenames:
                src = os.path.join(dirpath, filename)
                rel = os.path.relpath(src, shell_templates_dir)
                dst = os.path.join(output, rel)
                with open(src, "r", encoding="utf-8") as f:
                    write(dst, fill(f.read(), **subs))

    # -------------------------------------------------------------------------
    # Setup submodule
    # -------------------------------------------------------------------------
    print("\n>>> Adding Setup submodule...")
    run(["git", "submodule", "add", "--branch", "main", SETUP_URL, "Setup"], cwd=output)

    # -------------------------------------------------------------------------
    # Push shell repo
    # -------------------------------------------------------------------------
    print("\n>>> Pushing shell repo...")
    run(["git", "add", "."],                          cwd=output)
    run(["git", "commit", "-m", "Initial commit"],    cwd=output)
    run(["git", "push", "-u", "origin", "main"],      cwd=output)

    # -------------------------------------------------------------------------
    # Self-cleanup — delete the standalone Setup clone (now a submodule)
    # -------------------------------------------------------------------------
    print("\n>>> Cleaning up standalone Setup clone...")
    try:
        rmtree(SETUP_DIR)
        print("  Deleted.")
    except Exception as e:
        print(f"  Could not delete {SETUP_DIR}: {e}")
        print("  Safe to delete manually.")

    # -------------------------------------------------------------------------
    # Done
    # -------------------------------------------------------------------------
    print(f"""
==========================================================
  Done!

  Shell repo:  https://github.com/{args.org}/{shell_repo}
  Coordinator: https://github.com/{args.org}/{coordinator_repo}
  Local path:  {output}

  Next steps:
    cd {output}
    python Setup/deploy/deploy_all.py --overwrite

    Before running release automation, create these org Actions secrets
    with All repositories access:
      TCLI_AUTH_TOKEN
      SUBMODULE_UPDATE_TOKEN
      RELEASE_DISPATCH_TOKEN

  To add game submodules:
    git submodule add --branch main <url> Submodules/<name>
    python Setup/deploy/deploy_all.py --overwrite
==========================================================
""")


if __name__ == "__main__":
    main()
