# ModpackTools

Deployment, module scaffolding, release, and maintenance scripts for Hades II
modpack shell repos.

This repo is usually checked out as `ModpackTools/` inside a shell repo. Use
[`ModpackBootstrap`](https://github.com/h2-modpack/ModpackBootstrap) for the
one-time creation of a new pack workspace.

## What This Handles

ModpackTools is the ongoing toolbelt for an existing pack workspace:

- scaffold new module repos from the module template
- deploy local assets, manifests, profile links, and git hooks
- register or prune submodule entries
- validate release plans and platform dependency edges
- optionally configure GitHub Actions secrets

## Add A Module

From the shell repo root:

```bash
python ModpackTools/scaffold/new_module.py --package-id My_Module --title "My Module"
python ModpackTools/deploy/deploy_all.py --overwrite
```

`new_module.py` creates the GitHub repo from
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
python ModpackTools/deploy/deploy_all.py
python ModpackTools/deploy/deploy_all.py --overwrite
```

`deploy_all.py` refreshes shared assets, generated manifests, r2modman profile
links, and git hook configuration. Use `--overwrite` when regenerating files or
links that already exist.

On Linux/macOS, `./ModpackTools/lin.sh` is a shorthand for the same local deploy
path. On Windows, `ModpackTools/win.bat` is available and may require
Administrator permissions for symlinks.

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
GitHub user settings. ModpackTools can store or link existing secret values, but
it does not mint new PATs.

With All repositories access, every repo in the pack org can read the secrets.
The shell, coordinator, and module repos are covered automatically, so the
normal path does not need `github/deploy_secrets.py --link-org-secrets`.

## Alternative Secret Deployment

Use `github/deploy_secrets.py` only for tighter selected-repository access or
repo-level secret fallback.

For selected-repository org secrets, create the org secrets first:

- `TCLI_AUTH_TOKEN`
- `RELEASE_DISPATCH_TOKEN`

Then link them to this pack's repos:

```bash
python ModpackTools/github/deploy_secrets.py --link-org-secrets --dry-run
python ModpackTools/github/deploy_secrets.py --link-org-secrets
```

This links `TCLI_AUTH_TOKEN` to the coordinator and every `Submodules/*` repo,
and links `RELEASE_DISPATCH_TOKEN` to the shell repo.

Lib and Framework are excluded by default because they live in the shared
`h2-modpack` org. Add `--include-lib-framework` only when intentionally managing
those repos from this shell.

Fallback repo-level setup is also available:

```powershell
$env:TCLI_AUTH_TOKEN = "your-thunderstore-token"
python ModpackTools/github/deploy_secrets.py
```

To also set shell workflow secrets directly on the shell repo:

```powershell
$env:TCLI_AUTH_TOKEN = "your-thunderstore-token"
$env:RELEASE_DISPATCH_TOKEN = "your-github-dispatch-token"
python ModpackTools/github/deploy_secrets.py --include-shell
```

If token values are not supplied through environment variables, the script
prompts securely.

## Submodule Maintenance

If repos already exist under `Submodules/` but are not registered in
`.gitmodules`:

```bash
python ModpackTools/scaffold/register_submodules.py
```

After deleting module folders from `Submodules/`, prune stale entries:

```bash
python ModpackTools/scaffold/register_submodules.py --prune
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
| `lin.sh` | Run `deploy/deploy_all.py` on Linux/macOS |
| `win.bat` | Run `deploy/deploy_all.py` on Windows |
| `commit_submodules.py` | Commit and push all changed `Submodules/*` repos with one message |

Deployment helpers:

| File | Description |
|---|---|
| `deploy/deploy_all.py` | Full local deploy: assets, manifests, symlinks, git hooks |
| `deploy/deploy_assets.py` | Copy `icon.png` and `LICENSE` from ModpackTools root into every mod's `src/` |
| `deploy/deploy_manifests.py` | Generate `manifest.json` for every mod from `thunderstore.toml` |
| `deploy/deploy_links.py` | Create r2modman profile symlinks for every mod |
| `deploy/deploy_hooks.py` | Configure `.githooks` paths for every mod repo |
| `deploy/deploy_common.py` | Shared deploy utilities |
| `deploy/generate_manifest.py` | Generate a manifest for a single mod using structured TOML parsing |

GitHub automation helpers:

| File | Description |
|---|---|
| `github/deploy_secrets.py` | Optional helper for org-secret linking or repo-level GitHub Actions secrets |
| `github/release_all.py` | Shared pack-wide release dispatcher used by shell `Release All` workflows |
| `tests/test_release_all.py` | Dry-run planner tests for release target normalization and version gating |
| `validate_platform_versions.py` | Validate required platform dependency edges and print the checked-out version snapshot |

Scaffolding helpers:

| File | Description |
|---|---|
| `scaffold/new_module.py` | Scaffold a module repo from the template and register it as a submodule |
| `scaffold/register_submodules.py` | Register or prune `Submodules/` entries in `.gitmodules` |
| `scaffold/setup_common.py` | Shared scaffold utilities |

## Common Flags

Most scripts share these flags:

| Flag | Default | Description |
|---|---|---|
| `--overwrite` | off | Overwrite existing files or links instead of skipping |
| `--profile NAME` | `h2-dev` | r2modman profile to deploy into |
| `--dry-run` | off | Show what would happen without making changes, where supported |
