"""
Commit and push all Submodules/adamant-* repos with a shared commit message.
Skips repos with nothing to commit.

Usage:
    python Setup/commit_submodules.py "your commit message"
"""

import glob
import os
import subprocess
import sys


SETUP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR  = os.path.dirname(SETUP_DIR)


def discover_submodules():
    return sorted(glob.glob(os.path.join(ROOT_DIR, "Submodules", "adamant-*")))


def run(cmd, cwd):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Usage: python Setup/commit_submodules.py \"commit message\"")
        sys.exit(1)

    message    = sys.argv[1].strip()
    submodules = discover_submodules()

    if not submodules:
        print("No submodules found.")
        sys.exit(1)

    print(f"Committing {len(submodules)} submodules: \"{message}\"\n")

    succeeded = []
    skipped   = []
    failed    = []

    for path in submodules:
        name = os.path.basename(path)

        code, _, err = run(["git", "add", "-A"], cwd=path)
        if code != 0:
            print(f"  {name}: FAILED (git add): {err}")
            failed.append(name)
            continue

        code, out, _ = run(["git", "status", "--porcelain"], cwd=path)
        if not out:
            print(f"  {name}: nothing to commit, skipped")
            skipped.append(name)
            continue

        code, _, err = run(["git", "commit", "-m", message], cwd=path)
        if code != 0:
            print(f"  {name}: FAILED (git commit): {err}")
            failed.append(name)
            continue

        code, _, err = run(["git", "push"], cwd=path)
        if code != 0:
            print(f"  {name}: FAILED (git push): {err}")
            failed.append(name)
            continue

        print(f"  {name}: ok")
        succeeded.append(name)

    print(f"\n{'=' * 50}")
    print(f"  {len(succeeded)} pushed, {len(skipped)} skipped, {len(failed)} failed")
    if failed:
        print(f"  Failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
