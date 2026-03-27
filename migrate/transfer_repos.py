"""
Transfer all submodule repos from one GitHub org to another.

Reads submodule URLs from .gitmodules, filters those matching --from-org,
transfers each via `gh api`, and writes repos.txt with the new URLs and
local paths — ready for bulk_add.py to wire them into a new shell.

Usage (run from anywhere inside the shell repo):
  python Setup/migrate/transfer_repos.py --from-org h2-modpack --to-org new-org
  python Setup/migrate/transfer_repos.py --from-org h2-modpack --to-org new-org --dry-run

After running:
  cd <new-shell>
  python Setup/migrate/bulk_add.py --repos /path/to/repos.txt
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


def parse_submodules(from_org, to_org):
    """Return list of (repo_name, path, old_url, new_url, branch) for repos in from_org."""
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
        branch  = cfg.get(section, "branch") if cfg.has_option(section, "branch") else "main"
        m = re.match(r'https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$', old_url)
        if m and m.group(1) == from_org:
            repo    = m.group(2)
            new_url = f"https://github.com/{to_org}/{repo}.git"
            results.append((repo, path, old_url, new_url, branch))
    return results


def run(cmd, dry_run=False):
    print(f"  $ {' '.join(cmd)}")
    if not dry_run:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr.strip()}")
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Transfer submodule repos to a new GitHub org")
    parser.add_argument("--from-org", required=True, help="Source GitHub org")
    parser.add_argument("--to-org",   required=True, help="Destination GitHub org")
    parser.add_argument("--dry-run",  action="store_true", help="Show what would be transferred without doing it")
    args = parser.parse_args()

    entries = parse_submodules(args.from_org, args.to_org)

    if not entries:
        print(f"No submodules found with org '{args.from_org}' in .gitmodules.")
        sys.exit(0)

    print(f"\n  Transferring {len(entries)} repo(s) from {args.from_org} → {args.to_org}")
    if args.dry_run:
        print("  (dry run — no changes will be made)\n")
    else:
        print()

    for repo, path, _, _, _ in entries:
        print(f"  {args.from_org}/{repo}  →  {path}")

    if not args.dry_run:
        print()
        answer = input("  Proceed? [y/N] ").strip().lower()
        if answer != "y":
            print("  Aborted.")
            sys.exit(0)

    print()
    failed = []
    for repo, _, _, _, _ in entries:
        print(f">>> {args.from_org}/{repo} → {args.to_org}/{repo}")
        ok = run(["gh", "api", "--method", "POST",
                  "-H", "Accept: application/vnd.github+json",
                  "-H", "X-GitHub-Api-Version: 2022-11-28",
                  f"/repos/{args.from_org}/{repo}/transfer",
                  "-f", f"new_owner={args.to_org}"],
                 dry_run=args.dry_run)
        if not ok:
            failed.append(repo)

    print()
    if failed:
        print(f"  {len(failed)} failed: {', '.join(failed)}")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # Write repos.txt — new_url path branch, one entry per line
    # -------------------------------------------------------------------------
    repos_txt = os.path.join(ROOT_DIR, "repos.txt")
    lines = [f"{new_url} {path} {branch}" for _, path, _, new_url, branch in entries]

    if args.dry_run:
        print("  Dry run complete. Re-run without --dry-run to transfer.")
        print(f"\n  repos.txt would contain ({len(lines)} entries):")
        for line in lines:
            print(f"    {line}")
    else:
        with open(repos_txt, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        print(f"  All transferred.")
        print(f"  repos.txt written to: {repos_txt}")
        print(f"\n  Next steps:")
        print(f"    cd <new-shell>")
        print(f"    python Setup/migrate/bulk_add.py --repos {repos_txt}")
