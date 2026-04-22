"""
Configure GitHub Actions secrets for a modpack's GitHub repos.

Preferred mode links existing org-level selected secrets to the shell,
coordinator/core, and Submodules/* repos:

  python Setup/github/deploy_secrets.py --link-org-secrets

Fallback mode sets repo-level secrets by value. By default it sets
TCLI_AUTH_TOKEN on the coordinator/core repo and every Submodules/* repo:

  python Setup/github/deploy_secrets.py
"""

import argparse
import getpass
import os
import re
import subprocess
import sys


GITHUB_DIR = os.path.dirname(os.path.abspath(__file__))
SETUP_DIR = os.path.dirname(GITHUB_DIR)
ROOT_DIR = os.path.dirname(SETUP_DIR)


DEFAULT_PACKAGE_SECRET_NAME = "TCLI_AUTH_TOKEN"
DEFAULT_PACKAGE_SECRET_NAMES = [DEFAULT_PACKAGE_SECRET_NAME]
DEFAULT_SHELL_SECRET_NAMES = ["SUBMODULE_UPDATE_TOKEN", "RELEASE_DISPATCH_TOKEN"]
EXCLUDED_TOP_LEVEL = {"adamant-ModpackLib", "adamant-ModpackFramework"}


def discover_package_repos(include_lib_framework):
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


def infer_org(repo_slug):
    return repo_slug.split("/", 1)[0]


def get_repo_database_id(repo_slug):
    result = subprocess.run(
        ["gh", "repo", "view", repo_slug, "--json", "databaseId", "--jq", ".databaseId"],
        capture_output=True,
        text=True,
        check=True,
    )
    repo_id = result.stdout.strip()
    if not repo_id:
        raise RuntimeError(f"Could not resolve GitHub databaseId for {repo_slug}")
    return repo_id


def resolve_secret_value(secret_name, token_value, token_env_name):
    if token_value:
        value = token_value.strip()
        if value:
            return value
        raise ValueError("--token was provided but is empty.")

    env_name = token_env_name or secret_name
    env_value = os.environ.get(env_name)
    if env_value is not None:
        value = env_value.strip()
        if value:
            return value
        raise ValueError(
            f"Environment variable {env_name} is set but empty. Refusing to create blank secrets."
        )

    value = getpass.getpass(f"Enter {secret_name} value: ").strip()
    if value:
        return value

    raise ValueError(
        f"No secret value provided. Pass --token, set {env_name}, or enter a value when prompted."
    )


def set_secret_on_repo(repo_slug, secret_name, secret_value):
    print(f">>> Setting repo secret {secret_name} on {repo_slug}...")
    subprocess.run(
        ["gh", "secret", "set", secret_name, "--repo", repo_slug],
        input=secret_value,
        text=True,
        check=True,
    )


def link_org_secret_to_repo(org, repo_slug, secret_name):
    repo_id = get_repo_database_id(repo_slug)
    print(f">>> Linking org secret {secret_name} to {repo_slug}...")
    subprocess.run(
        [
            "gh",
            "api",
            "--method",
            "PUT",
            f"/orgs/{org}/actions/secrets/{secret_name}/repositories/{repo_id}",
        ],
        check=True,
    )


def print_targets(title, rows):
    print(title)
    print("-" * 72)
    for slug, rel_path, secret_names in rows:
        secrets = ", ".join(secret_names)
        print(f"  {slug}")
        print(f"    path    : {rel_path}")
        print(f"    secrets : {secrets}")
    print("-" * 72)


def build_target_rows(package_repos, shell_repo_slug, package_secret_names, shell_secret_names):
    package_rows = [
        (slug, os.path.relpath(path, ROOT_DIR), package_secret_names)
        for path, slug in package_repos
    ]
    shell_rows = []
    if shell_repo_slug and shell_secret_names:
        shell_rows.append((shell_repo_slug, ".", shell_secret_names))
    return package_rows, shell_rows


def repo_set_mode(args, package_repos, shell_repo_slug, package_secret_names, shell_secret_names):
    package_rows, shell_rows = build_target_rows(
        package_repos, shell_repo_slug, package_secret_names, shell_secret_names
    )
    print_targets("Repo-level secrets to set", package_rows + shell_rows)

    if args.dry_run:
        print("Dry-run only. No secrets changed.")
        return

    if len(package_secret_names) != 1:
        raise ValueError("Repo-level mode supports one package secret at a time.")

    package_secret_name = package_secret_names[0]
    package_secret_value = resolve_secret_value(
        package_secret_name, args.token, args.token_env
    )
    for _, slug in package_repos:
        set_secret_on_repo(slug, package_secret_name, package_secret_value)

    if shell_repo_slug:
        if args.shell_token and len(shell_secret_names) != 1:
            raise ValueError(
                "--shell-token can only be used with one shell secret. Pass --shell-secret-name."
            )
        if args.shell_token_env and len(shell_secret_names) != 1:
            raise ValueError(
                "--shell-token-env can only be used with one shell secret. Pass --shell-secret-name."
            )

        for shell_secret_name in shell_secret_names:
            shell_secret_value = resolve_secret_value(
                shell_secret_name, args.shell_token, args.shell_token_env
            )
            set_secret_on_repo(shell_repo_slug, shell_secret_name, shell_secret_value)


def org_link_mode(args, package_repos, shell_repo_slug, package_secret_names, shell_secret_names):
    org = args.org or infer_org(shell_repo_slug)
    package_rows, shell_rows = build_target_rows(
        package_repos, shell_repo_slug, package_secret_names, shell_secret_names
    )
    print(f"Org-level selected secrets to link from {org}")
    print_targets("Targets", package_rows + shell_rows)

    if args.dry_run:
        print("Dry-run only. No secrets linked.")
        return

    for _, slug in package_repos:
        for secret_name in package_secret_names:
            link_org_secret_to_repo(org, slug, secret_name)

    for secret_name in shell_secret_names:
        link_org_secret_to_repo(org, shell_repo_slug, secret_name)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Configure GitHub Actions secrets for the shell, coordinator/core, "
            "and Submodules/* repos."
        )
    )
    parser.add_argument(
        "--link-org-secrets",
        action="store_true",
        help=(
            "Link existing org-level selected secrets to the correct repos. "
            "This is the preferred mode for one-org-per-pack setups."
        ),
    )
    parser.add_argument(
        "--org",
        default=None,
        help="GitHub org that owns the org-level secrets (default: shell repo owner).",
    )
    parser.add_argument(
        "--secret-name",
        default=DEFAULT_PACKAGE_SECRET_NAME,
        help=f"Package repo secret name for repo-level mode (default: {DEFAULT_PACKAGE_SECRET_NAME}).",
    )
    parser.add_argument(
        "--package-secret",
        action="append",
        default=None,
        help=(
            "Package repo secret name for org-link mode. May be repeated. "
            f"Default: {', '.join(DEFAULT_PACKAGE_SECRET_NAMES)}."
        ),
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Package secret value for repo-level mode. Prefer --token-env or prompt.",
    )
    parser.add_argument(
        "--token-env",
        default=None,
        help=(
            "Environment variable to read the package secret value from "
            "(default: package secret name)."
        ),
    )
    parser.add_argument(
        "--include-lib-framework",
        action="store_true",
        help="Also target adamant-ModpackLib and adamant-ModpackFramework.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print targets without changing GitHub secrets.",
    )
    parser.add_argument(
        "--include-shell",
        action="store_true",
        help=(
            "Also set shell workflow secrets in repo-level mode. "
            "Org-link mode always includes the shell repo."
        ),
    )
    parser.add_argument(
        "--shell-secret",
        action="append",
        default=None,
        help=(
            "Shell repo secret name for org-link mode. May be repeated. "
            f"Default: {', '.join(DEFAULT_SHELL_SECRET_NAMES)}."
        ),
    )
    parser.add_argument(
        "--shell-secret-name",
        default=None,
        help=(
            "Shell repo secret name for repo-level mode. If omitted with "
            f"--include-shell, sets {', '.join(DEFAULT_SHELL_SECRET_NAMES)}."
        ),
    )
    parser.add_argument(
        "--shell-token",
        default=None,
        help="Shell secret value for repo-level mode when setting one shell secret.",
    )
    parser.add_argument(
        "--shell-token-env",
        default=None,
        help=(
            "Environment variable to read one shell secret value from "
            "(default: shell secret name)."
        ),
    )
    args = parser.parse_args()

    targets = discover_package_repos(args.include_lib_framework)
    if not targets:
        print("No releasable package repos found.")
        sys.exit(1)

    package_repos = [(path, get_repo_slug(path)) for path in targets]
    shell_repo_slug = get_repo_slug(ROOT_DIR)

    if args.link_org_secrets:
        package_secret_names = args.package_secret or DEFAULT_PACKAGE_SECRET_NAMES
        shell_secret_names = args.shell_secret or DEFAULT_SHELL_SECRET_NAMES
        org_link_mode(args, package_repos, shell_repo_slug, package_secret_names, shell_secret_names)
    else:
        package_secret_names = [args.secret_name]
        shell_secret_names = []
        if args.include_shell:
            shell_secret_names = (
                [args.shell_secret_name]
                if args.shell_secret_name
                else DEFAULT_SHELL_SECRET_NAMES
            )
        repo_set_mode(
            args,
            package_repos,
            shell_repo_slug if args.include_shell else None,
            package_secret_names,
            shell_secret_names,
        )

    print("")
    print("Done.")


if __name__ == "__main__":
    main()
