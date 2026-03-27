"""
Rewire local git config after transferring repos to a new GitHub org.

Updates:
  1. .gitmodules  — submodule URLs
  2. .git/config  — via `git submodule sync`
  3. Each submodule's local origin remote

Usage (run from anywhere inside the shell repo):
  python Setup/migrate/rewire.py --from-org h2-modpack --to-org new-org
  python Setup/migrate/rewire.py --from-org h2-modpack --to-org new-org --dry-run

Run this after transfer_repos.py (or any time you want to point submodules
at a different org without transferring on GitHub).
"""

import os
import sys
import re
import argparse
import subprocess
import configparser


SETUP_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR   = os.path.dirname(SETUP_DIR)
GITMODULES = os.path.join(ROOT_DIR, ".gitmodules")


def run(cmd, cwd=None, dry_run=False):
    print(f"  $ {' '.join(cmd)}")
    if not dry_run:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr.strip()}")
            return False
    return True


def get_submodule_entries(from_org, to_org):
    """Return list of (path, old_url, new_url) for submodules matching from_org."""
    if not os.path.exists(GITMODULES):
        print("ERROR: .gitmodules not found.")
        sys.exit(1)

    cfg = configparser.ConfigParser()
    cfg.read(GITMODULES)

    results = []
    for section in cfg.sections():
        if not cfg.has_option(section, "url") or not cfg.has_option(section, "path"):
            continue
        old_url = cfg.get(section, "url")
        path    = cfg.get(section, "path")
        m = re.match(r'(https://github\.com/)([^/]+)(/.*)', old_url)
        if m and m.group(2) == from_org:
            new_url = m.group(1) + to_org + m.group(3)
            results.append((path, old_url, new_url))
    return results


def main():
    parser = argparse.ArgumentParser(description="Rewire submodule URLs to a new GitHub org")
    parser.add_argument("--from-org", required=True, help="Old GitHub org")
    parser.add_argument("--to-org",   required=True, help="New GitHub org")
    parser.add_argument("--dry-run",  action="store_true", help="Show changes without applying")
    args = parser.parse_args()

    entries = get_submodule_entries(args.from_org, args.to_org)

    if not entries:
        print(f"No submodule URLs found with org '{args.from_org}' in .gitmodules.")
        sys.exit(0)

    print(f"\n  Rewiring {len(entries)} submodule(s): {args.from_org} → {args.to_org}")
    if args.dry_run:
        print("  (dry run — no changes will be made)\n")
    else:
        print()

    for path, old_url, new_url in entries:
        print(f"  {path}")
        print(f"    {old_url}")
        print(f"    → {new_url}")

    if not args.dry_run:
        print()
        answer = input("  Proceed? [y/N] ").strip().lower()
        if answer != "y":
            print("  Aborted.")
            sys.exit(0)

    # -------------------------------------------------------------------------
    # Step 1: Rewrite .gitmodules
    # -------------------------------------------------------------------------
    print("\n>>> Updating .gitmodules...")
    if not args.dry_run:
        with open(GITMODULES, encoding="utf-8") as f:
            content = f.read()
        updated = content.replace(
            f"https://github.com/{args.from_org}/",
            f"https://github.com/{args.to_org}/",
        )
        with open(GITMODULES, "w", encoding="utf-8", newline="\n") as f:
            f.write(updated)
        print("  Done.")
    else:
        print(f"  (would replace 'github.com/{args.from_org}/' → 'github.com/{args.to_org}/' in .gitmodules)")

    # -------------------------------------------------------------------------
    # Step 2: Sync .git/config from .gitmodules
    # -------------------------------------------------------------------------
    print("\n>>> Running git submodule sync...")
    run(["git", "submodule", "sync"], cwd=ROOT_DIR, dry_run=args.dry_run)

    # -------------------------------------------------------------------------
    # Step 3: Update origin remote in each checked-out submodule
    # -------------------------------------------------------------------------
    print("\n>>> Updating local origin remotes...")
    for path, old_url, new_url in entries:
        abs_path = os.path.join(ROOT_DIR, path)
        if not os.path.isdir(abs_path):
            print(f"  skip  {path}  (not checked out)")
            continue
        print(f"  {path}")
        run(["git", "remote", "set-url", "origin", new_url],
            cwd=abs_path, dry_run=args.dry_run)

    print()
    if args.dry_run:
        print("  Dry run complete. Re-run without --dry-run to apply.")
    else:
        print("  Done. Verify with: git submodule foreach 'git remote -v'")


if __name__ == "__main__":
    main()
