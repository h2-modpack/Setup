#!/usr/bin/env python3
"""Check whether a Thunderstore package version already exists.

Release workflows use this before `tcli publish` so a rerun can repair git
release state after a successful Thunderstore publish without trying to upload
the same immutable package version twice.
"""

from __future__ import annotations

import argparse
import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class ThunderstoreCheckError(Exception):
    def __init__(self, title: str, message: str):
        super().__init__(message)
        self.title = title
        self.message = message


@dataclass(frozen=True)
class PackageIdentity:
    repository: str
    namespace: str
    name: str
    version: str

    @property
    def full_name(self) -> str:
        return f"{self.namespace}-{self.name}-{self.version}"


def read_package_identity(config_path: Path, expected_tag: str | None) -> PackageIdentity:
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)

    package = data.get("package")
    if not isinstance(package, dict):
        raise ThunderstoreCheckError("Invalid Thunderstore config", "thunderstore.toml must contain [package].")

    namespace = package.get("namespace")
    name = package.get("name")
    version = package.get("versionNumber")
    if not all(isinstance(value, str) and value.strip() for value in (namespace, name, version)):
        raise ThunderstoreCheckError(
            "Invalid Thunderstore config",
            "thunderstore.toml must define package.namespace, package.name, and package.versionNumber.",
        )

    if expected_tag is not None and version != expected_tag:
        raise ThunderstoreCheckError(
            "Thunderstore version mismatch",
            f"thunderstore.toml has versionNumber {version}, expected {expected_tag}.",
        )

    publish = data.get("publish")
    repository = "https://thunderstore.io"
    if isinstance(publish, dict) and isinstance(publish.get("repository"), str) and publish["repository"].strip():
        repository = publish["repository"].strip()

    return PackageIdentity(
        repository=repository.rstrip("/"),
        namespace=namespace,
        name=name,
        version=version,
    )


def release_url(identity: PackageIdentity) -> str:
    namespace = quote(identity.namespace, safe="")
    name = quote(identity.name, safe="")
    version = quote(identity.version, safe="")
    return f"{identity.repository}/api/experimental/package/{namespace}/{name}/{version}/"


def thunderstore_release_exists(identity: PackageIdentity) -> bool:
    request = Request(
        release_url(identity),
        headers={"User-Agent": "adamant-modpack-release-check/1.0"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            return 200 <= response.status < 300
    except HTTPError as exc:
        if exc.code == 404:
            return False
        raise ThunderstoreCheckError(
            "Thunderstore check failed",
            f"Thunderstore returned HTTP {exc.code} while checking {identity.full_name}.",
        ) from exc
    except URLError as exc:
        raise ThunderstoreCheckError(
            "Thunderstore check failed",
            f"Could not reach Thunderstore while checking {identity.full_name}: {exc.reason}",
        ) from exc


def write_github_output(path: str | None, identity: PackageIdentity, published: bool) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"published={'true' if published else 'false'}\n")
        handle.write(f"package={identity.full_name}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check Thunderstore package version publication state.")
    parser.add_argument("--config", default="thunderstore.toml", help="Thunderstore config path.")
    parser.add_argument("--tag", default=None, help="Expected package version.")
    parser.add_argument(
        "--github-output",
        default=None,
        help="GitHub Actions output file. Defaults to GITHUB_OUTPUT when set.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        identity = read_package_identity(Path(args.config), args.tag)
        published = thunderstore_release_exists(identity)
        output_path = args.github_output if args.github_output is not None else os.environ.get("GITHUB_OUTPUT")
        write_github_output(output_path, identity, published)
        state = "already exists" if published else "does not exist"
        print(f"Thunderstore package {identity.full_name} {state}.")
        return 0
    except ThunderstoreCheckError as exc:
        print(f"::error title={exc.title}::{exc.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
