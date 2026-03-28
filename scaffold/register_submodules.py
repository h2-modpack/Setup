"""
Register existing repos in Submodules/ as git submodules and sync the Core
module's Thunderstore dependency list.

Scans Submodules/ for git repos not yet registered in .gitmodules, reads their
remote URL, and runs `git submodule add --force` to register them.

With --prune, also removes .gitmodules entries whose Submodules/ folder is gone.

After register/prune, updates the [package.dependencies] block in the Core
module's thunderstore.toml. A managed marker block is used so infrastructure
deps are never touched:

    # -- submodules-start --
    adamant-QoL = "1.0.0"
    # -- submodules-end --

The Core module is discovered automatically: any root-level folder whose
thunderstore.toml has a package name ending in "Core".

Repos with no remote configured are skipped with a warning — create the GitHub
repo first, add it as `origin`, then re-run this script.

Usage (run from anywhere inside the shell repo):
  python Setup/scaffold/register_submodules.py
  python Setup/scaffold/register_submodules.py --prune
"""

import os
import re
import sys
import subprocess
import configparser
import tomllib


SETUP_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR       = os.path.dirname(SETUP_DIR)
SUBMODULES_DIR = os.path.join(ROOT_DIR, "Submodules")
GITMODULES     = os.path.join(ROOT_DIR, ".gitmodules")

MARKER_START = "# -- submodules-start --"
MARKER_END   = "# -- submodules-end --"


# =============================================================================
# HELPERS
# =============================================================================

def run(cmd, cwd=None, capture=False):
    return subprocess.run(cmd, cwd=cwd, capture_output=capture, text=True)


def git(args, cwd=None):
    return run(["git"] + args, cwd=cwd, capture=True)


def registered_paths():
    """Return set of forward-slash submodule paths already in .gitmodules."""
    if not os.path.exists(GITMODULES):
        return set()
    cfg = configparser.ConfigParser()
    cfg.read(GITMODULES)
    paths = set()
    for section in cfg.sections():
        if cfg.has_option(section, "path"):
            paths.add(cfg.get(section, "path").replace("\\", "/"))
    return paths


def remote_url(repo_path):
    result = git(["remote", "get-url", "origin"], cwd=repo_path)
    return result.stdout.strip() if result.returncode == 0 else None


def current_branch(repo_path):
    result = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
    branch = result.stdout.strip() if result.returncode == 0 else ""
    return branch if branch and branch != "HEAD" else "main"


def find_core_toml():
    """Find the Core module's thunderstore.toml in root-level folders."""
    for entry in os.scandir(ROOT_DIR):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        toml_path = os.path.join(entry.path, "thunderstore.toml")
        if not os.path.exists(toml_path):
            continue
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
        name = data.get("package", {}).get("name", "")
        if name.endswith("Core"):
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


def current_submodule_names():
    """Return sorted list of submodule folder names in Submodules/."""
    names = []
    for entry in sorted(os.scandir(SUBMODULES_DIR), key=lambda e: e.name):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if not os.path.isdir(os.path.join(entry.path, ".git")):
            continue
        names.append(entry.name)
    return names


def update_core_deps():
    """Sync the managed submodule block in the Core thunderstore.toml."""
    print("Syncing Core module dependencies...")
    print("  Detecting Core module: scanning root-level folders for a thunderstore.toml")
    print("  whose package name ends in 'Core'...")

    core_toml = find_core_toml()
    if not core_toml:
        print("  WARN  No Core module found, skipping dep sync.")
        return

    print(f"  found   {os.path.relpath(core_toml, ROOT_DIR)}")
    print(f"  Replacing managed block between '{MARKER_START}' and '{MARKER_END}'")
    print("  (infrastructure deps above the markers are left untouched)")

    names = current_submodule_names()
    lines = [f'{name} = "{submodule_version(name)}"' for name in names]
    block = MARKER_START + "\n" + "\n".join(lines) + "\n" + MARKER_END

    text = open(core_toml, encoding="utf-8").read()

    if MARKER_START in text:
        # Replace existing managed block
        pattern  = re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END)
        new_text = re.sub(pattern, block, text, flags=re.DOTALL)
    else:
        # First run: insert block before the next section after [package.dependencies]
        dep_header = "[package.dependencies]"
        if dep_header not in text:
            print("  WARN  No [package.dependencies] section in Core toml, skipping dep sync.")
            return
        m = re.search(r'(\[package\.dependencies\].*?)(\n\[)', text, re.DOTALL)
        if m:
            new_text = text[:m.start(2)] + "\n" + block + "\n" + text[m.start(2):]
        else:
            # [package.dependencies] is the last section
            new_text = text.rstrip() + "\n" + block + "\n"

    open(core_toml, "w", encoding="utf-8").write(new_text)
    print(f"  synced  Core deps ({len(names)} submodules)  →  {os.path.relpath(core_toml, ROOT_DIR)}")
    print()
    print("  NOTE: Run `python Setup/deploy/deploy_all.py --overwrite` to deploy changes to the game.")


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Register submodules and optionally prune removed ones")
    parser.add_argument("--prune", action="store_true", help="Remove .gitmodules entries whose folder no longer exists")
    args = parser.parse_args()

    if not os.path.isdir(SUBMODULES_DIR):
        print("No Submodules/ directory found.")
        sys.exit(0)

    already_registered = registered_paths()

    # -------------------------------------------------------------------------
    # Prune: entries in .gitmodules with no corresponding folder
    # -------------------------------------------------------------------------
    if args.prune:
        to_prune = [
            rel for rel in already_registered
            if rel.startswith("Submodules/") and not os.path.isdir(os.path.join(ROOT_DIR, rel))
        ]

        if to_prune:
            print(f"Pruning {len(to_prune)} removed submodule(s):\n")
            for rel in sorted(to_prune):
                print(f"  {rel}")

            print()
            failed_prune = []
            for rel in sorted(to_prune):
                print(f">>> deinit + rm {rel} ...", end=" ", flush=True)
                r1 = git(["submodule", "deinit", "-f", rel], cwd=ROOT_DIR)
                r2 = git(["rm", "-f", rel], cwd=ROOT_DIR)
                if r1.returncode == 0 and r2.returncode == 0:
                    print("done.")
                else:
                    print("FAILED.")
                    if r1.returncode != 0:
                        print(f"    deinit: {r1.stderr.strip()}")
                    if r2.returncode != 0:
                        print(f"    rm:     {r2.stderr.strip()}")
                    failed_prune.append(rel)

            print()
            if failed_prune:
                print(f"  {len(failed_prune)} prune(s) failed — check errors above.")
                sys.exit(1)
            else:
                print(f"  Pruned. Re-reading registered paths...")
                already_registered = registered_paths()
        else:
            print("Nothing to prune.")

    # -------------------------------------------------------------------------
    # Register: folders in Submodules/ not yet in .gitmodules
    # -------------------------------------------------------------------------
    to_register = []
    warnings    = []

    for entry in sorted(os.scandir(SUBMODULES_DIR), key=lambda e: e.name):
        name = entry.name
        path = entry.path
        rel  = f"Submodules/{name}"

        if not entry.is_dir() or name.startswith("."):
            continue

        if not os.path.isdir(os.path.join(path, ".git")):
            continue  # not a git repo, silently skip (.gitkeep etc.)

        if rel in already_registered:
            print(f"  ok      {rel}")
            continue

        url = remote_url(path)
        if not url:
            warnings.append(name)
            print(f"  WARN    {name}  — no remote origin. Create a GitHub repo,")
            print(f"          run `git remote add origin <url>` inside it, then re-run.")
            continue

        branch = current_branch(path)
        to_register.append((name, rel, url, branch))

    if warnings:
        print()

    if not to_register:
        print("\nNothing new to register.")
    else:
        print(f"\nRegistering {len(to_register)} submodule(s):\n")
        for name, rel, url, branch in to_register:
            print(f"  {rel}")
            print(f"    url:    {url}")
            print(f"    branch: {branch}")

        print()

        failed = []
        for name, rel, url, branch in to_register:
            print(f">>> {rel} ...", end=" ", flush=True)
            result = run(
                ["git", "submodule", "add", "--force", "--branch", branch, url, rel],
                cwd=ROOT_DIR,
            )
            if result.returncode == 0:
                print("done.")
            else:
                print("FAILED.")
                print(f"    {result.stderr.strip()}")
                failed.append(rel)

        print()
        if failed:
            print(f"  {len(failed)} failed — check errors above.")
            sys.exit(1)

    # -------------------------------------------------------------------------
    # Sync Core module dependencies
    # -------------------------------------------------------------------------
    print()
    update_core_deps()


if __name__ == "__main__":
    main()
