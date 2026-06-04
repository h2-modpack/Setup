"""
Scaffolds a new modpack shell repo with Lib, Framework, and a coordinator.
Creates the coordinator GitHub repo automatically via the gh CLI.

Clone Setup next to where you want the new pack, then run:

  git clone https://github.com/h2-modpack/Setup.git
  python Setup/scaffold/new_pack.py \
    --pack-id speedrun \
    --pack-name "Speedrun" \
    --coordinator-package Speedrun_Modpack \
    --team adamantSpeedrun \
    --org h2pack-speedrun

The shell repo is created as a sibling of the Setup folder:
  ../speedrun-modpack/

The standalone Setup clone is deleted at the end - it re-enters as a submodule.

Naming contract:
  --pack-id is the internal Framework id (lowercase letters, numbers, hyphens).
  --pack-name is the in-game/window display name.
  --coordinator-package is the Thunderstore package/repo/folder suffix.
  --team is the Thunderstore namespace/team for pack-owned packages.
  --org is the GitHub org where pack repos are created.

  Given --pack-id "speedrun", --coordinator-package "Speedrun_Modpack",
  and --team "adamantSpeedrun":
    Shell repo:        speedrun-modpack
    Coordinator ID:    adamantSpeedrun-Speedrun_Modpack
    Coordinator repo:  adamantSpeedrun-Speedrun_Modpack
    Lib folder:        adamant-ModpackLib
    Framework folder:  adamant-ModpackFramework

After running:
  cd ../speedrun-modpack
  python Setup/deploy/deploy_all.py --overwrite
"""

import os
import sys
import shutil
import argparse
import json
import re
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
# Use {{PLACEHOLDER}} markers - simple .replace(), no f-string conflicts with Lua.

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
{{SHARED_NAMESPACE}}-ModpackLib = "{{LIB_VERSION}}"
{{SHARED_NAMESPACE}}-ModpackFramework = "{{FRAMEWORK_VERSION}}"

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

def validate_pack_id(value):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value or ""):
        raise ValueError("--pack-id must contain lowercase letters, numbers, and single hyphen separators only")


def validate_single_line(value, flag):
    if value is None or not value.strip():
        raise ValueError(f"{flag} must not be empty")
    if "\n" in value or "\r" in value:
        raise ValueError(f"{flag} must be a single line")


def validate_team(value):
    if not re.fullmatch(r"[A-Za-z0-9_]+", value or ""):
        raise ValueError("--team must contain only letters, numbers, and underscores")
    if value.startswith("_") or value.endswith("_"):
        raise ValueError("--team must not start or end with '_'")


def validate_coordinator_package(value):
    if not re.fullmatch(r"[A-Za-z0-9_]+", value or ""):
        raise ValueError("--coordinator-package must contain only letters, numbers, and underscores")
    if value.startswith("_") or value.endswith("_") or "__" in value:
        raise ValueError("--coordinator-package must not start/end with '_' or contain repeated underscores")


def validate_org(value):
    if not re.fullmatch(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", value or ""):
        raise ValueError("--org must contain letters, numbers, and single hyphen separators only")


def coordinator_id(team, coordinator_package):
    return f"{team}-{coordinator_package}"


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
    parser.add_argument("--pack-id",   required=True,  help="Pack ID used in Framework.createPack - single word preferred (e.g. 'speedrun')")
    parser.add_argument("--pack-name", required=True, help="In-game/window display name for the pack (e.g. 'Speedrun')")
    parser.add_argument("--coordinator-package", required=True, help="Coordinator Thunderstore package/repo suffix (e.g. 'Speedrun_Modpack')")
    parser.add_argument("--team", required=True, help="Pack Thunderstore namespace/team (e.g. 'adamantSpeedrun')")
    parser.add_argument("--shared-namespace", default="adamant", help="Shared infrastructure namespace for Lib/Framework deps (default: adamant)")
    parser.add_argument("--org",       required=True,        help="GitHub org (e.g. 'my-org')")
    args = parser.parse_args()

    try:
        validate_pack_id(args.pack_id)
        validate_single_line(args.pack_name, "--pack-name")
        validate_coordinator_package(args.coordinator_package)
        validate_team(args.team)
        validate_org(args.org)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    title  = args.pack_name.strip()
    name   = args.coordinator_package
    output = os.path.join(ROOT_DIR, f"{args.pack_id}-modpack")

    shell_repo       = f"{args.pack_id}-modpack"
    shell_url        = f"https://github.com/{args.org}/{shell_repo}.git"
    coord_id         = coordinator_id(args.team, name)
    coordinator_repo = coord_id                                             # GitHub repo name = Thunderstore ID = local folder
    coordinator_url  = f"https://github.com/{args.org}/{coordinator_repo}.git"

    print(f"""
  What will be created and deployed
  ---------------------------------------------
  Pack identity
    Internal pack id       : {args.pack_id}
    In-game pack name      : {title}

  Thunderstore
    Team / namespace       : {args.team}
    Coordinator package    : {name}
    Coordinator full ID    : {coord_id}
    Shared deps            : {args.shared_namespace}-ModpackLib, {args.shared_namespace}-ModpackFramework

  Local
    Output folder          : {output}
    Coordinator folder     : {os.path.join(output, coord_id)}

  GitHub repos (will be created under {args.org}/)
    Shell                  : {shell_repo}
    Coordinator            : {coordinator_repo}  (github.com/{args.org}/{coordinator_repo})

  Submodule folders
    Lib                    : adamant-ModpackLib
    Framework              : adamant-ModpackFramework
    Coordinator            : {coord_id}

  Side effects
    Creates GitHub repos, initializes commits, pushes to origin, wires
    submodules, and deletes the standalone Setup clone after Setup is added
    back as a submodule.
  ---------------------------------------------""")

    answer = input("  Proceed with these side effects? [y/N] ").strip().lower()
    if answer != "y":
        print("  Aborted.")
        sys.exit(0)

    confirmation = input(f"  Type the coordinator full ID to confirm ({coord_id}): ").strip()
    if confirmation != coord_id:
        print("  Confirmation did not match. Aborted.")
        sys.exit(0)

    if os.path.exists(output):
        print(f"\nERROR: {output} already exists.")
        sys.exit(1)

    os.makedirs(output)

    # -------------------------------------------------------------------------
    # Shell repo - create on GitHub, init locally, set remote
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
    # Coordinator - generate files, push to new GitHub repo, then add as submodule
    # -------------------------------------------------------------------------
    coord_dir = os.path.join(output, coord_id)

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
        COORD_ID     = coord_id,
        PACK_ID      = args.pack_id,
        WINDOW_TITLE = title,
        NAMESPACE    = args.team,
        NAME         = name,
        ORG          = args.org,
        SHELL_REPO   = shell_repo,
        COORD_REPO   = coordinator_repo,
        SHARED_NAMESPACE = args.shared_namespace,
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
        "namespace":      args.team,
        "name":           name,
        "description":    f"{title} modpack coordinator.",
        "version_number": "1.0.0",
        "dependencies": [
            "Hell2Modding-Hell2Modding-1.0.78",
            "LuaENVY-ENVY-1.2.0",
            "SGG_Modding-Chalk-2.1.1",
            "SGG_Modding-ReLoad-1.0.2",
            "SGG_Modding-ModUtil-4.0.1",
            f"{args.shared_namespace}-ModpackLib-{lib_version}",
            f"{args.shared_namespace}-ModpackFramework-{framework_version}",
        ],
        "website_url": f"https://github.com/{args.org}/{coordinator_repo}",
        "FullName": coord_id,
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
    run(["git", "submodule", "add", "--branch", "main", coordinator_url, coord_id], cwd=output)

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
    # Self-cleanup - delete the standalone Setup clone (now a submodule)
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
        Thunderstore token for the pack namespace/team ({args.team}).
        Used by each coordinator/module release workflow to publish packages.

      RELEASE_DISPATCH_TOKEN
        GitHub fine-grained PAT for {args.org} with Actions read/write and
        Contents read access. Used by the shell Release All workflow to
        dispatch coordinator/module release workflows.

    Prefer org-level secrets over repo-level secrets for this pack org. If a
    repo-level secret with the same name exists, GitHub Actions uses the
    repo-level value and it can mask the org-level one.

  To add game submodules:
    git submodule add --branch main <url> Submodules/<name>
    python Setup/deploy/deploy_all.py --overwrite
==========================================================
""")


if __name__ == "__main__":
    main()
