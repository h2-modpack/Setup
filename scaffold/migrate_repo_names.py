"""
One-time migration: rename GitHub repos so each repo name matches its local
submodule folder name.

Before: GitHub repo = BiomeControl      local = Submodules/adamant-BiomeControl
After:  GitHub repo = adamant-BiomeControl  local = Submodules/adamant-BiomeControl (unchanged)

Run from the shell repo root:
  python Setup/scaffold/migrate_repo_names.py --org my-org [--dry-run]

Options:
  --org      GitHub org that owns the submodule repos
  --dry-run  Print planned renames without executing them
"""

import os
import re
import sys
import argparse
import subprocess
from setup_common import run


SETUP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR  = os.path.dirname(SETUP_DIR)


def read_gitmodules():
    path = os.path.join(ROOT_DIR, ".gitmodules")
    if not os.path.exists(path):
        print(f"ERROR: .gitmodules not found at {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_gitmodules(content):
    path = os.path.join(ROOT_DIR, ".gitmodules")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def parse_submodules(content):
    """Return list of {path, url} dicts parsed from .gitmodules content."""
    result = []
    for block in re.split(r'(?=\[submodule\s)', content):
        if not block.strip():
            continue
        path_m = re.search(r'path\s*=\s*(.+)', block)
        url_m  = re.search(r'url\s*=\s*(.+)', block)
        if path_m and url_m:
            result.append({
                "path": path_m.group(1).strip(),
                "url":  url_m.group(1).strip(),
            })
    return result


def repo_stem(url):
    """Extract bare repo name from a git URL (strips path and .git suffix)."""
    name = url.rstrip("/").split("/")[-1]
    return name[:-4] if name.endswith(".git") else name


def main():
    parser = argparse.ArgumentParser(
        description="Rename GitHub repos to match local submodule folder names")
    parser.add_argument("--org",     required=True,  help="GitHub org owning the repos (e.g. h2-modpack)")
    parser.add_argument("--dry-run", action="store_true", help="Print planned renames without executing")
    args = parser.parse_args()

    content    = read_gitmodules()
    submodules = parse_submodules(content)

    if not submodules:
        print("No submodules found in .gitmodules.")
        sys.exit(0)

    print(f"\n  Submodules found: {len(submodules)}\n")

    renames = []
    for sm in submodules:
        # Skip any submodule that isn't inside the "Submodules" folder
        if not sm["path"].startswith("Submodules/"):
            continue

        expected = os.path.basename(sm["path"])   # adamant-BiomeControl
        current  = repo_stem(sm["url"])            # BiomeControl
        
        if expected == current:
            print(f"  [ok]     {current}")
        else:
            print(f"  [rename] {current}  ->  {expected}")
            renames.append({
                "current":  current,
                "expected": expected,
                "old_url":  sm["url"],
                "new_url":  sm["url"].replace(f"/{current}", f"/{expected}"),
            })

    if not renames:
        print("\nAll repo names are already correct. Nothing to do.")
        return

    print(f"\n  {len(renames)} repo(s) will be renamed.")

    if args.dry_run:
        print("  --dry-run: no changes made.")
        return

    answer = input("\n  Proceed? [y/N] ").strip().lower()
    if answer != "y":
        print("  Aborted.")
        sys.exit(0)

    # -------------------------------------------------------------------------
    # Rename each repo on GitHub and patch .gitmodules in memory
    # -------------------------------------------------------------------------
    for r in renames:
        print(f"\n>>> Renaming {args.org}/{r['current']}  ->  {r['expected']}...")
        run(["gh", "repo", "rename", r["expected"],
             "--repo", f"{args.org}/{r['current']}", "--yes"])
        content = content.replace(r["old_url"], r["new_url"])

    # -------------------------------------------------------------------------
    # Write updated .gitmodules and sync
    # -------------------------------------------------------------------------
    write_gitmodules(content)
    print("\n>>> .gitmodules updated.")

    print("\n>>> Syncing submodule remote URLs...")
    subprocess.run(["git", "submodule", "sync"], cwd=ROOT_DIR, check=True)

    print(f"""
==========================================================
  Done! {len(renames)} repo(s) renamed.

  Finish up:
    git add .gitmodules
    git commit -m "chore: align GitHub repo names with local submodule folders"

  Each other contributor must run:
    git submodule sync
    git submodule update --remote
==========================================================
""")


if __name__ == "__main__":
    main()