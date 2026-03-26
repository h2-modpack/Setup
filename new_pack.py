"""
Scaffolds a new modpack shell repo with Lib, Framework, and a coordinator.
Creates the coordinator GitHub repo automatically via the gh CLI.

Usage:
  python Setup/new_pack.py \\
    --output ~/Projects/my-pack \\
    --pack-id "my-pack" \\
    --title "My Pack" \\
    --namespace mynamespace \\
    [--name Modpack_Core] \\
    [--org h2-modpack]

Example (this modpack):
  python Setup/new_pack.py \\
    --output ~/Projects/h2-modular-modpack \\
    --pack-id "h2-modpack" \\
    --title "Adamant Modpack" \\
    --namespace adamant \\
    --name Modpack_Core \\
    --org h2-modpack

After running:
  cd <output>
  python Setup/deploy_all.py --overwrite
"""

import os
import sys
import shutil
import subprocess
import argparse
import json


LIB_URL      = "https://github.com/h2-modpack/h2-modpack-Lib.git"
FRAMEWORK_URL = "https://github.com/h2-modpack/h2-modpack-Framework.git"
SETUP_URL    = "https://github.com/h2-modpack/Setup.git"


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
websiteUrl = "https://github.com/{{ORG}}/{{PACK_ID}}-coordinator"
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

def main():
    parser = argparse.ArgumentParser(description="Scaffold a new modpack shell repo")
    parser.add_argument("--output",          required=True,               help="Path to create the new shell repo")
    parser.add_argument("--pack-id",         required=True,               help="Pack ID used in Framework.init (e.g. 'my-pack')")
    parser.add_argument("--title",           required=True,               help="Window title (e.g. 'My Pack')")
    parser.add_argument("--namespace",       required=True,               help="Thunderstore namespace")
    parser.add_argument("--name",      default="Modpack_Core", help="Coordinator mod name (default: Modpack_Core)")
    parser.add_argument("--org",       default="h2-modpack",   help="GitHub org for the coordinator repo (default: h2-modpack)")
    args = parser.parse_args()

    output           = os.path.abspath(args.output)
    coordinator_id   = f"{args.namespace}-{args.name}"
    coordinator_repo = f"{args.pack_id}-coordinator"
    coordinator_url  = f"https://github.com/{args.org}/{coordinator_repo}.git"

    print(f"\n  New pack: {args.title}")
    print(f"  Output:   {output}")
    print(f"  Pack ID:  {args.pack_id}")
    print(f"  Coord:    {coordinator_id} -> {args.org}/{coordinator_repo}\n")

    if os.path.exists(output):
        print(f"ERROR: {output} already exists.")
        sys.exit(1)

    os.makedirs(output)

    # -------------------------------------------------------------------------
    # Git init
    # -------------------------------------------------------------------------
    print(">>> Initialising git repo...")
    run(["git", "init", "-b", "main"], cwd=output)

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
        "--description", f"{args.title} modpack coordinator",
    ])

    # Generate coordinator files into a local git repo and push first,
    # so the remote has a commit before we add it as a submodule.
    print(f"\n>>> Initialising coordinator and pushing initial commit...")
    subs = dict(
        COORD_ID     = coordinator_id,
        PACK_ID      = args.pack_id,
        WINDOW_TITLE = args.title,
        NAMESPACE    = args.namespace,
        NAME         = args.name,
        ORG          = args.org,
    )
    write(os.path.join(coord_dir, "src", "main.lua"),        fill(MAIN_LUA,           **subs))
    write(os.path.join(coord_dir, "src", "config.lua"),      fill(CONFIG_LUA,         **subs))
    write(os.path.join(coord_dir, "thunderstore.toml"),      fill(THUNDERSTORE_TOML,  **subs))
    write(os.path.join(coord_dir, "CHANGELOG.md"),           CHANGELOG_MD)

    manifest = {
        "namespace":      args.namespace,
        "name":           args.name,
        "description":    f"{args.title} modpack coordinator.",
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
    shutil.rmtree(coord_dir)

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
    # Done
    # -------------------------------------------------------------------------
    print(f"""
==========================================================
  Done! Shell repo created at:
  {output}

  Coordinator repo: https://github.com/{args.org}/{coordinator_repo}

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
