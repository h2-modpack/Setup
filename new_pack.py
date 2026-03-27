"""
Scaffolds a new modpack shell repo with Lib, Framework, and a coordinator.
Creates the coordinator GitHub repo automatically via the gh CLI.

Clone Setup next to where you want the new pack, then run:

  git clone https://github.com/h2-modpack/Setup.git
  python Setup/new_pack.py --pack-id "my-pack" --namespace mynamespace

The shell repo is created as a sibling of the Setup folder:
  ../my-pack-modpack/

The standalone Setup clone is deleted at the end — it re-enters as a submodule.

Optional overrides:
  [--title "My Pack"]           default: title-case of pack-id
  [--name my_pack_coordinator]  default: <pack_id>_coordinator
  [--org h2-modpack]            default: h2-modpack

Example (this modpack, --name overridden for backwards compat):
  python Setup/new_pack.py \\
    --pack-id "h2-modpack" \\
    --namespace adamant \\
    --title "Adamant Modpack" \\
    --name Modpack_Core

After running:
  cd ../h2-modpack-modpack
  python Setup/deploy_all.py --overwrite
"""

import os
import sys
import stat
import shutil
import subprocess
import argparse
import json


SETUP_DIR     = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR      = os.path.dirname(SETUP_DIR)

LIB_URL       = "https://github.com/h2-modpack/h2-modpack-Lib.git"
FRAMEWORK_URL = "https://github.com/h2-modpack/h2-modpack-Framework.git"
SETUP_URL     = "https://github.com/h2-modpack/Setup.git"


# =============================================================================
# TEMPLATES
# =============================================================================
# Use {{PLACEHOLDER}} markers — simple .replace(), no f-string conflicts with Lua.

MAIN_LUA = """\
-- =============================================================================
-- {{COORD_ID}}: Modpack Coordinator
-- =============================================================================
-- Thin coordinator: wires globals, owns config and def, delegates everything
-- else to adamant-Modpack_Framework.

local mods = rom.mods
mods['SGG_Modding-ENVY'].auto()

---@diagnostic disable: lowercase-global
rom = rom
_PLUGIN = _PLUGIN
game = rom.game
modutil = mods['SGG_Modding-ModUtil']
chalk   = mods['SGG_Modding-Chalk']
reload  = mods['SGG_Modding-ReLoad']

config = chalk.auto('config.lua')
public.config = config

local def = {
    NUM_PROFILES    = #config.Profiles,
    defaultProfiles = {},
}

local PACK_ID = "{{PACK_ID}}"

local function init()
    local Framework = mods['adamant-Modpack_Framework']
    Framework.init({
        packId      = PACK_ID,
        windowTitle = "{{WINDOW_TITLE}}",
        config      = config,
        def         = def,
        modutil     = modutil,
    })
end

local loader = reload.auto_single()
modutil.once_loaded.game(function()
    local Framework = mods['adamant-Modpack_Framework']
    rom.gui.add_imgui(Framework.getRenderer(PACK_ID))
    rom.gui.add_to_menu_bar(Framework.getMenuBar(PACK_ID))
    loader.load(init, init)
end)
"""

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
websiteUrl = "https://github.com/{{ORG}}/{{PACK_ID}}-modpack-coordinator"
containsNsfwContent = false

[package.dependencies]
Hell2Modding-Hell2Modding = "1.0.78"
LuaENVY-ENVY = "1.2.0"
SGG_Modding-Chalk = "2.1.1"
SGG_Modding-ReLoad = "1.0.2"
SGG_Modding-ModUtil = "4.0.1"
adamant-Modpack_Lib = "1.0.0"
adamant-Modpack_Framework = "1.0.0"


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

## 1.0.0

- Initial release
"""



# =============================================================================
# HELPERS
# =============================================================================

def rmtree(path):
    """shutil.rmtree with read-only override (required for .git/ on Windows)."""
    def force_remove(func, p, _):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onexc=force_remove)


def fill(template, **kwargs):
    for key, value in kwargs.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def run(cmd, cwd=None):
    print(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


# =============================================================================
# MAIN
# =============================================================================

def pack_id_to_title(pack_id):
    """'run-director' -> 'Run Director'"""
    return " ".join(w.capitalize() for w in pack_id.replace("_", "-").split("-"))


def pack_id_to_name(pack_id):
    """'run-director' -> 'run_director_coordinator'"""
    return pack_id.replace("-", "_") + "_coordinator"


def main():
    parser = argparse.ArgumentParser(description="Scaffold a new modpack shell repo")
    parser.add_argument("--pack-id",   required=True,  help="Pack ID used in Framework.init (e.g. 'run-director')")
    parser.add_argument("--namespace", required=True,  help="Thunderstore namespace (e.g. 'adamant')")
    parser.add_argument("--title",     default=None,   help="Window title (default: title-case of pack-id)")
    parser.add_argument("--name",      default=None,   help="Coordinator mod name (default: <pack_id>_coordinator)")
    parser.add_argument("--org",       default="h2-modpack", help="GitHub org (default: h2-modpack)")
    args = parser.parse_args()

    title  = args.title or pack_id_to_title(args.pack_id)
    name   = args.name  or pack_id_to_name(args.pack_id)
    output = os.path.join(ROOT_DIR, f"{args.pack_id}-modpack")

    shell_repo       = f"{args.pack_id}-modpack"
    shell_url        = f"https://github.com/{args.org}/{shell_repo}.git"
    coordinator_id   = f"{args.namespace}-{name}"
    coordinator_repo = f"{args.pack_id}-modpack-coordinator"
    coordinator_url  = f"https://github.com/{args.org}/{coordinator_repo}.git"

    print(f"\n  New pack: {title}")
    print(f"  Output:   {output}")
    print(f"  Pack ID:  {args.pack_id}")
    print(f"  Shell:    {args.org}/{shell_repo}")
    print(f"  Coord:    {coordinator_id} -> {args.org}/{coordinator_repo}\n")

    if os.path.exists(output):
        print(f"ERROR: {output} already exists.")
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
    run(["git", "submodule", "add", "--branch", "main", LIB_URL, "adamant-modpack-Lib"], cwd=output)

    print("\n>>> Adding Framework submodule...")
    run(["git", "submodule", "add", "--branch", "main", FRAMEWORK_URL, "adamant-modpack-Framework"], cwd=output)

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
        WINDOW_TITLE = title,
        NAMESPACE    = args.namespace,
        NAME         = name,
        ORG          = args.org,
    )
    # Inline templates (Lua/TOML — tightly coupled to new_pack.py logic)
    write(os.path.join(coord_dir, "src", "main.lua"),     fill(MAIN_LUA,          **subs))
    write(os.path.join(coord_dir, "src", "config.lua"),   fill(CONFIG_LUA,        **subs))
    write(os.path.join(coord_dir, "thunderstore.toml"),   fill(THUNDERSTORE_TOML, **subs))
    write(os.path.join(coord_dir, "CHANGELOG.md"),        CHANGELOG_MD)

    # File templates from Setup/templates/coordinator/ — fill() is a no-op on files without placeholders
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
            "adamant-Modpack_Lib-1.0.0",
            "adamant-Modpack_Framework-1.0.0",
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
    python Setup/deploy_all.py --overwrite

  To add game submodules:
    git submodule add --branch main <url> Submodules/<name>
    python Setup/deploy_all.py --overwrite
==========================================================
""")


if __name__ == "__main__":
    main()
