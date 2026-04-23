# Setup

Deployment, scaffolding, and maintenance scripts for Hades II modpack shell repos.
This repo is usually checked out as `Setup/` inside a shell repo.

## What This Handles

Setup is the shared toolbelt for a pack workspace:

- scaffold a new shell repo and coordinator repo
- scaffold new module repos from the module template
- deploy local assets, manifests, profile links, and git hooks
- register or prune submodule entries
- optionally configure GitHub Actions secrets

The shell's submodule update workflow needs a pack org secret named `SUBMODULE_UPDATE_TOKEN` once you want GitHub Actions to open pointer-update PRs.

## Create A New Pack

Use one GitHub org per modpack. `new_pack.py` expects that org to already exist; it does not create the org.

Create the empty GitHub org first, then scaffold the pack from a standalone Setup clone:

```bash
git clone https://github.com/h2-modpack/Setup
python Setup/scaffold/new_pack.py --pack-id "my-pack" --namespace mynamespace --org my-org
cd ../my-pack-modpack
python Setup/deploy/deploy_all.py --overwrite
```

`new_pack.py` creates the shell repo and coordinator repo inside the org, wires Lib, Framework, coordinator, and Setup as submodules, and pushes the initial shell commit. The standalone Setup clone is deleted at the end because Setup re-enters the shell as a submodule.

Shared Lib and Framework live in the shared `h2-modpack` org and are managed separately from each pack org.

## Add A Module

From the shell repo root:

```bash
python Setup/scaffold/new_module.py --name MyModName --pack-id my-pack --namespace adamant --org my-org
python Setup/deploy/deploy_all.py --overwrite
```

`new_module.py` creates the GitHub repo from the module template, fills in module identity, commits the initial repo, registers it under `Submodules/`, and syncs the coordinator dependency block.

Generated modules inherit the current module template contract: split `main.lua` / `data.lua` / `logic.lua` / `ui.lua`, host-owned hook registration, and the standard module CI baseline.

## Local Deployment

After cloning, scaffolding, or changing a pack locally, run the deploy step from the shell repo root:

```bash
python Setup/deploy/deploy_all.py
python Setup/deploy/deploy_all.py --overwrite
```

`deploy_all.py` refreshes shared assets, generated manifests, r2modman profile links, and git hook configuration. Use `--overwrite` when regenerating files or links that already exist.

On Linux/macOS, `./Setup/lin.sh` is a shorthand for the same local deploy path. On Windows, `Setup/win.bat` is available and may require Administrator permissions for symlinks.

## Remote Maintenance And Release

Remote maintenance starts before the first Thunderstore release if you want GitHub Actions to keep shell submodule pointers current.

Create `SUBMODULE_UPDATE_TOKEN` as a GitHub Actions org secret with **All repositories** access once you want the shell `Update Submodules` workflow to open pointer-update PRs. That workflow validates the pack, pushes an `automation/update-submodules` branch, and opens or updates the PR.

Normal release maintenance is:

1. Module, coordinator, Lib, or Framework repos change and are pushed.
2. The shell `Update Submodules` workflow opens or updates the pointer PR using `SUBMODULE_UPDATE_TOKEN`.
3. Merge that PR into `main` after checks pass.
4. Run `Release All` from the shell repo when publishing the pack.

`Release All` dispatches the child release workflows. Core/coordinator release depends on the module pointers being current in the shell, so keep the submodule update PR merged before publishing.

Before publishing releases, also add these GitHub Actions org secrets with **All repositories** access:

- `TCLI_AUTH_TOKEN`
- `RELEASE_DISPATCH_TOKEN`

The GitHub PAT value for `RELEASE_DISPATCH_TOKEN` is still created manually in GitHub user settings. Setup can store or link existing secret values, but it does not mint new PATs.

With All repositories access, every current and future repo in the pack org can read the secrets. The shell, coordinator, and module repos are covered automatically, so the normal path does not need `github/deploy_secrets.py --link-org-secrets`.

## Alternative Secret Deployment

Use `github/deploy_secrets.py` only for tighter selected-repository access or repo-level secret fallback.

For selected-repository org secrets, create the org secrets first:

- `TCLI_AUTH_TOKEN`
- `SUBMODULE_UPDATE_TOKEN`
- `RELEASE_DISPATCH_TOKEN`

Then link them to this pack's repos:

```bash
python Setup/github/deploy_secrets.py --link-org-secrets --dry-run
python Setup/github/deploy_secrets.py --link-org-secrets
```

This links `TCLI_AUTH_TOKEN` to the coordinator and every `Submodules/*` repo, and links `SUBMODULE_UPDATE_TOKEN` plus `RELEASE_DISPATCH_TOKEN` to the shell repo.

Lib and Framework are excluded by default because they live in the shared `h2-modpack` org. Add `--include-lib-framework` only when intentionally managing those repos from this shell.

Fallback repo-level setup is also available:

```powershell
$env:TCLI_AUTH_TOKEN = "your-thunderstore-token"
python Setup/github/deploy_secrets.py
```

To also set shell workflow secrets directly on the shell repo:

```powershell
$env:TCLI_AUTH_TOKEN = "your-thunderstore-token"
$env:SUBMODULE_UPDATE_TOKEN = "your-github-pr-token"
$env:RELEASE_DISPATCH_TOKEN = "your-github-dispatch-token"
python Setup/github/deploy_secrets.py --include-shell
```

If token values are not supplied through environment variables, the script prompts securely.

## Submodule Maintenance

If repos already exist under `Submodules/` but are not registered in `.gitmodules`:

```bash
python Setup/scaffold/register_submodules.py
```

After deleting module folders from `Submodules/`, prune stale entries:

```bash
python Setup/scaffold/register_submodules.py --prune
```

To commit and push a shared change across all module repos:

```bash
python Setup/commit_submodules.py "fix: update config schema"
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
| `deploy/deploy_assets.py` | Copy `icon.png` and `LICENSE` from Setup root into every mod's `src/` |
| `deploy/deploy_manifests.py` | Generate `manifest.json` for every mod from `thunderstore.toml` |
| `deploy/deploy_links.py` | Create r2modman profile symlinks for every mod |
| `deploy/deploy_hooks.py` | Configure `.githooks` paths for every mod repo |
| `deploy/deploy_common.py` | Shared deploy utilities |
| `deploy/generate_manifest.py` | Generate a manifest for a single mod |

GitHub automation helpers:

| File | Description |
|---|---|
| `github/deploy_secrets.py` | Optional helper for org-secret linking or repo-level GitHub Actions secrets |
| `github/release_all.py` | Shared pack-wide release dispatcher used by shell `Release All` workflows |
| `tests/test_release_all.py` | Dry-run planner tests for release target normalization and version gating |

Scaffolding helpers:

| File | Description |
|---|---|
| `scaffold/new_pack.py` | Scaffold a complete shell repo with coordinator and shared submodules |
| `scaffold/new_module.py` | Scaffold a module repo from the template and register it as a submodule |
| `scaffold/register_submodules.py` | Register or prune `Submodules/` entries in `.gitmodules` |
| `scaffold/setup_common.py` | Shared scaffold utilities |

Templates:

| Folder | Used for |
|---|---|
| `templates/coordinator/` | Coordinator files copied by `new_pack.py` |
| `templates/shell/` | Shell files copied by `new_pack.py` |

## Common Flags

Most scripts share these flags:

| Flag | Default | Description |
|---|---|---|
| `--overwrite` | off | Overwrite existing files or links instead of skipping |
| `--profile NAME` | `h2-dev` | r2modman profile to deploy into |
| `--dry-run` | off | Show what would happen without making changes, where supported |
