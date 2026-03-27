"""
Add multiple submodules to a shell repo from a repos.txt file.

repos.txt format (produced by transfer_repos.py):
  <url> <path> <branch>

One entry per line. Lines starting with # are ignored.

Usage (run from the new shell repo root):
  python Setup/migrate/bulk_add.py --repos /path/to/repos.txt
  python Setup/migrate/bulk_add.py --repos /path/to/repos.txt --dry-run
"""

import os
import sys
import argparse
import subprocess


SETUP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR  = os.path.dirname(SETUP_DIR)


def run(cmd, cwd=None, dry_run=False):
    print(f"  $ {' '.join(cmd)}")
    if not dry_run:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr.strip()}")
            return False
    return True


def parse_repos_txt(path):
    entries = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 3:
                print(f"  WARNING: line {lineno} malformed (expected url path branch), skipping: {line}")
                continue
            entries.append(tuple(parts))
    return entries


def main():
    parser = argparse.ArgumentParser(description="Bulk-add submodules from repos.txt")
    parser.add_argument("--repos",   required=True, help="Path to repos.txt (produced by transfer_repos.py)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be added without doing it")
    args = parser.parse_args()

    if not os.path.exists(args.repos):
        print(f"ERROR: {args.repos} not found.")
        sys.exit(1)

    entries = parse_repos_txt(args.repos)

    if not entries:
        print("No entries found in repos.txt.")
        sys.exit(0)

    print(f"\n  Adding {len(entries)} submodule(s) to {ROOT_DIR}")
    if args.dry_run:
        print("  (dry run — no changes will be made)\n")
    else:
        print()

    for url, path, branch in entries:
        print(f"  {path}  ({url})")

    print()
    failed = []
    for url, path, branch in entries:
        print(f">>> {path}")
        ok = run(
            ["git", "submodule", "add", "--branch", branch, url, path],
            cwd=ROOT_DIR,
            dry_run=args.dry_run,
        )
        if not ok:
            failed.append(path)

    print()
    if failed:
        print(f"  {len(failed)} failed: {', '.join(failed)}")
        sys.exit(1)
    else:
        if args.dry_run:
            print("  Dry run complete. Re-run without --dry-run to add.")
        else:
            print("  All submodules added.")
            print("  Next: python Setup/deploy/deploy_all.py --overwrite")


if __name__ == "__main__":
    main()
