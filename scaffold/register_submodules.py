"""
Register existing repos in Submodules/ as git submodules.

Scans Submodules/ for git repos not yet registered in .gitmodules, reads their
remote URL, and runs `git submodule add --force` to register them.

Repos with no remote configured are skipped with a warning — create the GitHub
repo first, add it as `origin`, then re-run this script.

Usage (run from anywhere inside the shell repo):
  python Setup/register_submodules.py
"""

import os
import sys
import subprocess
import configparser


SETUP_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR       = os.path.dirname(SETUP_DIR)
SUBMODULES_DIR = os.path.join(ROOT_DIR, "Submodules")
GITMODULES     = os.path.join(ROOT_DIR, ".gitmodules")


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


# =============================================================================
# MAIN
# =============================================================================

def main():
    if not os.path.isdir(SUBMODULES_DIR):
        print("No Submodules/ directory found.")
        sys.exit(0)

    already_registered = registered_paths()
    to_register = []
    warnings    = []

    for name in sorted(os.listdir(SUBMODULES_DIR)):
        path = os.path.join(SUBMODULES_DIR, name)
        rel  = f"Submodules/{name}"

        if not os.path.isdir(path) or name.startswith("."):
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
        return

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
    else:
        print(f"  All registered. Run `python Setup/deploy_all.py --overwrite` to deploy.")


if __name__ == "__main__":
    main()
