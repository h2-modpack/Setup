"""Shared module roster discovery for shell composition tooling."""

from __future__ import annotations

import tomllib
import configparser
from dataclasses import dataclass
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = TOOLS_DIR.parent
GITMODULES = ROOT_DIR / ".gitmodules"


@dataclass(frozen=True)
class PackageInfo:
    namespace: str
    name: str
    version: str

    @property
    def thunderstore_id(self) -> str:
        return f"{self.namespace}-{self.name}"


@dataclass(frozen=True)
class CoordinatorPackage:
    path: Path
    toml_path: Path
    package: PackageInfo


@dataclass(frozen=True)
class ModuleRepo:
    folder_name: str
    path: Path
    package: PackageInfo | None

    @property
    def dependency_id(self) -> str:
        if self.package is None:
            return self.folder_name
        return self.package.thunderstore_id

    @property
    def dependency_version(self) -> str:
        if self.package is None:
            return "1.0.0"
        return self.package.version


def registered_paths(gitmodules_path: Path = GITMODULES) -> list[Path]:
    if not gitmodules_path.is_file():
        return []

    config = configparser.ConfigParser()
    config.read(gitmodules_path)
    paths: list[Path] = []
    for section in config.sections():
        if config.has_option(section, "path"):
            paths.append(Path(config.get(section, "path").replace("\\", "/")))
    return sorted(paths, key=lambda path: path.as_posix())


def read_toml(path: Path) -> dict:
    with path.open("rb") as file:
        return tomllib.load(file)


def read_package_info(toml_path: Path, *, default_version: str = "1.0.0") -> PackageInfo:
    data = read_toml(toml_path)
    package = data.get("package", {})
    namespace = package.get("namespace")
    name = package.get("name")
    version = package.get("versionNumber", default_version)
    if not isinstance(namespace, str) or not namespace:
        raise RuntimeError(f"{toml_path} is missing package.namespace")
    if not isinstance(name, str) or not name:
        raise RuntimeError(f"{toml_path} is missing package.name")
    if not isinstance(version, str) or not version:
        version = default_version
    return PackageInfo(namespace=namespace, name=name, version=version)


def registered_module_paths(root_dir: Path = ROOT_DIR, gitmodules_path: Path | None = None) -> list[Path]:
    source = gitmodules_path or (root_dir / ".gitmodules")
    return [root_dir / path for path in registered_paths(source) if path.parts[:1] == ("Submodules",)]


def module_repo_from_dir(path: Path) -> ModuleRepo:
    toml_path = path / "thunderstore.toml"
    package = read_package_info(toml_path) if toml_path.is_file() else None
    return ModuleRepo(folder_name=path.name, path=path, package=package)


def discover_module_repos(root_dir: Path = ROOT_DIR) -> list[ModuleRepo]:
    return [module_repo_from_dir(path) for path in registered_module_paths(root_dir)]


def find_coordinator_package(root_dir: Path = ROOT_DIR, *, team: str | None = None) -> CoordinatorPackage | None:
    matches: list[CoordinatorPackage] = []
    for path in registered_paths(root_dir / ".gitmodules"):
        if path.parts[:1] == ("Submodules",):
            continue
        entry = root_dir / path
        if not entry.is_dir():
            continue
        toml_path = entry / "thunderstore.toml"
        if not toml_path.is_file():
            continue
        package = read_package_info(toml_path)
        if package.name.endswith("_Modpack") and (team is None or package.namespace == team):
            matches.append(CoordinatorPackage(path=entry, toml_path=toml_path, package=package))

    if not matches:
        return None
    if len(matches) > 1:
        paths = ", ".join(str(match.toml_path) for match in matches)
        raise RuntimeError(f"multiple coordinator thunderstore.toml files matched: {paths}")
    return matches[0]
