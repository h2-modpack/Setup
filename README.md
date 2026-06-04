# ModpackTools

Deployment, module scaffolding, release, and maintenance scripts for Hades II
modpack shell repos.

This repo is usually checked out as `ModpackTools/` inside a shell repo. Use
[`ModpackBootstrap`](https://github.com/h2-modpack/ModpackBootstrap) for the
one-time creation of a new pack workspace.

New users should start with the
[`ModpackBootstrap` Getting Started guide](https://github.com/h2-modpack/ModpackBootstrap/blob/main/docs/GETTING_STARTED.md),
then return here for ongoing pack maintenance commands.

## What This Handles

ModpackTools is the ongoing toolbelt for an existing pack workspace:

- scaffold new module repos from the module template
- stage package assets for local deploy, generate manifests, link profiles, and configure git hooks
- register or prune submodule entries
- validate release plans and platform dependency edges

## Add A Module

From the shell repo root:

```bash
python ModpackTools/new_module/create.py --package-id My_Module --title "My Module"
python ModpackTools/local_deploy/deploy_all.py --overwrite
```

`create.py` creates the GitHub repo from
[`ModpackModuleTemplate`](https://github.com/h2-modpack/ModpackModuleTemplate),
fills in module identity, commits the initial repo, registers it under
`Submodules/`, and syncs the coordinator dependency block.

Generated module package names do not include the pack prefix because the pack
team already carries that identity. For example, in a pack using
`team = adamantSpeedrun`, `--package-id LiveSplit --title "LiveSplit"` creates
`adamantSpeedrun-LiveSplit`. The package id is also the Lib/Framework module id.

## Local Deployment

After cloning, scaffolding, or changing a pack locally, run the deploy step from
the shell repo root:

```bash
python ModpackTools/local_deploy/deploy_all.py
python ModpackTools/local_deploy/deploy_all.py --overwrite
```

`deploy_all.py` stages each package's root `icon.png` and `LICENSE` into
`src/`, refreshes generated manifests, updates r2modman profile links, and
configures git hooks. Use `--overwrite` when regenerating files or links that
already exist.

## Remote Maintenance And Release

Normal release maintenance is:

1. Module, coordinator, Lib, or Framework repos change and are pushed.
2. Update and commit the shell submodule pointers as part of that development work.
3. Run `Release All` from the shell repo when publishing the pack.

`Release All` validates the checked-out shell snapshot before dispatching child
release workflows. The dependency validator checks that required Thunderstore
dependency edges exist, and prints the checked-out package versions plus current
source pins for auditability. It does not require exact pin equality because
Thunderstore resolves package dependencies to the latest available version.

Before publishing releases, also add these GitHub Actions org secrets with
**All repositories** access:

- `TCLI_AUTH_TOKEN`
- `RELEASE_DISPATCH_TOKEN`

The GitHub PAT value for `RELEASE_DISPATCH_TOKEN` is still created manually in
GitHub user settings.

With All repositories access, every repo in the pack org can read the secrets.
The shell, coordinator, and module repos are covered automatically.

## Submodule Maintenance

If repos already exist under `Submodules/` but are not registered in
`.gitmodules`:

```bash
python ModpackTools/new_module/register_submodules.py
```

After deleting module folders from `Submodules/`, prune stale entries:

```bash
python ModpackTools/new_module/register_submodules.py --prune
```

To commit and push a shared change across all module repos:

```bash
python ModpackTools/commit_submodules.py "fix: update config schema"
```

Clean module repos are skipped.

## File Reference

Entry points:

| File | Description |
|---|---|
| `commit_submodules.py` | Commit and push all changed `Submodules/*` repos with one message |

Deployment helpers:

| File | Description |
|---|---|
| `local_deploy/deploy_all.py` | Full local deploy: staged package assets, manifests, symlinks, git hooks |
| `local_deploy/steps/` | Implementation modules used by `deploy_all.py` |

GitHub automation helpers:

| File | Description |
|---|---|
| `github/release_all.py` | Shared pack-wide release dispatcher used by shell `Release All` workflows |
| `tests/test_release_all.py` | Dry-run planner tests for release target normalization and version gating |
| `validate_platform_versions.py` | Validate required platform dependency edges and print the checked-out version snapshot |

Scaffolding helpers:

| File | Description |
|---|---|
| `new_module/create.py` | Scaffold a module repo from the template and register it as a submodule |
| `new_module/register_submodules.py` | Register or prune `Submodules/` entries in `.gitmodules` |
| `new_module/coordinator_deps.py` | Sync the coordinator's managed module dependency block |

## Common Flags

Most scripts share these flags:

| Flag | Default | Description |
|---|---|---|
| `--overwrite` | off | Overwrite existing files or links instead of skipping |
| `--profile NAME` | `h2-dev` | r2modman profile to deploy into |
| `--dry-run` | off | Show what would happen without making changes, where supported |
