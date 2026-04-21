"""
Configure GitHub Actions secrets for a modpack's GitHub repos.

By default this targets the coordinator/core repo plus every repo in Submodules/.
Lib and Framework are intentionally excluded unless --include-lib-framework is used.
The shell repo can be targeted separately for cross-repo dispatch secrets.
"""

import argparse
import getpass
import os
import re
import subprocess
import sys

from deploy_common import ROOT_DIR


DEFAULT_SECRET_NAME = "TCLI_AUTH_TOKEN"
DEFAULT_SHELL_SECRET_NAME = "RELEASE_DISPATCH_TOKEN"
EXCLUDED_TOP_LEVEL = {"adamant-ModpackLib", "adamant-ModpackFramework"}


def discover_target_repos(include_lib_framework):
    targets = []

    for entry in sorted(os.listdir(ROOT_DIR)):
        path = os.path.join(ROOT_DIR, entry)
        if not os.path.isdir(path):
            continue
        if not os.path.isfile(os.path.join(path, "thunderstore.toml")):
            continue
        if not include_lib_framework and entry in EXCLUDED_TOP_LEVEL:
            continue
        targets.append(path)

    submodules_dir = os.path.join(ROOT_DIR, "Submodules")
    if os.path.isdir(submodules_dir):
        for entry in sorted(os.listdir(submodules_dir)):
            path = os.path.join(submodules_dir, entry)
            if os.path.isfile(os.path.join(path, "thunderstore.toml")):
                targets.append(path)

    return targets


def get_repo_slug(repo_dir):
    result = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    remote = result.stdout.strip()

    patterns = [
        r"^https://github\.com/([^/]+/[^/]+?)(?:\.git)?$",
        r"^git@github\.com:([^/]+/[^/]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.match(pattern, remote)
        if match:
            return match.group(1)

    raise ValueError(f"Could not parse GitHub remote for {repo_dir}: {remote}")


def resolve_secret_value(secret_name, token_value, token_env_name):
    if token_value:
        value = token_value.strip()
        if value:
            return value
        raise ValueError("--token was provided but is empty.")

    env_value = os.environ.get(token_env_name)
    if env_value is not None:
        value = env_value.strip()
        if value:
            return value
        raise ValueError(
            f"Environment variable {token_env_name} is set but empty. Refusing to create blank secrets."
        )

    prompt = f"Enter {secret_name} value: "
    value = getpass.getpass(prompt).strip()
    if value:
        return value

    raise ValueError(
        f"No secret value provided. Pass --token, set {token_env_name}, or enter a value when prompted."
    )


def set_secret_on_repo(repo_slug, secret_name, secret_value):
    print(f">>> Setting {secret_name} on {repo_slug}...")
    subprocess.run(
        ["gh", "secret", "set", secret_name, "--repo", repo_slug],
        input=secret_value,
        text=True,
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Set a GitHub Actions secret on the coordinator repo and every Submodules/* repo."
    )
    parser.add_argument(
        "--secret-name",
        default=DEFAULT_SECRET_NAME,
        help=f"Secret name to set (default: {DEFAULT_SECRET_NAME})",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Secret value to apply. Prefer --token-env or interactive prompt to avoid shell history leaks.",
    )
    parser.add_argument(
        "--token-env",
        default=DEFAULT_SECRET_NAME,
        help=f"Environment variable to read the secret value from (default: {DEFAULT_SECRET_NAME})",
    )
    parser.add_argument(
        "--include-lib-framework",
        action="store_true",
        help="Also set the secret on adamant-ModpackLib and adamant-ModpackFramework.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the target repos without changing any GitHub secrets.",
    )
    parser.add_argument(
        "--include-shell",
        action="store_true",
        help=f"Also set {DEFAULT_SHELL_SECRET_NAME} on the shell repo.",
    )
    parser.add_argument(
        "--shell-secret-name",
        default=DEFAULT_SHELL_SECRET_NAME,
        help=f"Shell-repo secret name to set when --include-shell is used (default: {DEFAULT_SHELL_SECRET_NAME})",
    )
    parser.add_argument(
        "--shell-token",
        default=None,
        help="Shell secret value to apply. Prefer --shell-token-env or interactive prompt to avoid shell history leaks.",
    )
    parser.add_argument(
        "--shell-token-env",
        default=DEFAULT_SHELL_SECRET_NAME,
        help=f"Environment variable to read the shell secret value from (default: {DEFAULT_SHELL_SECRET_NAME})",
    )
    args = parser.parse_args()

    targets = discover_target_repos(args.include_lib_framework)
    if not targets:
        print("No releasable repos found.")
        sys.exit(1)

    repo_slugs = [(path, get_repo_slug(path)) for path in targets]
    shell_repo_slug = get_repo_slug(ROOT_DIR) if args.include_shell else None

    print("Release target repos")
    print("-" * 52)
    for path, slug in repo_slugs:
        print(f"  {slug}  <-  {os.path.relpath(path, ROOT_DIR)}")
    print("-" * 52)

    if shell_repo_slug:
        print("Shell repo secret target")
        print("-" * 52)
        print(f"  {shell_repo_slug}  <-  .")
        print("-" * 52)

    if args.dry_run:
        print("Dry-run only. No secrets changed.")
        return

    secret_value = resolve_secret_value(args.secret_name, args.token, args.token_env)

    for _, slug in repo_slugs:
        set_secret_on_repo(slug, args.secret_name, secret_value)

    if shell_repo_slug:
        shell_secret_value = resolve_secret_value(
            args.shell_secret_name, args.shell_token, args.shell_token_env
        )
        set_secret_on_repo(shell_repo_slug, args.shell_secret_name, shell_secret_value)

    print("")
    print("Done.")


if __name__ == "__main__":
    main()
