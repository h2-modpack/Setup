# Setup

Deployment and scaffolding scripts for modpack shell repos.
This repo lives at `Setup/` as a submodule in every shell repo it manages.

---

## File reference

### Entry points
| File | Description |
|---|---|
| `lin.sh` | Run `deploy/deploy_all.py` on Linux/macOS (handles python2/3, warns on missing root) |
| `win.bat` | Run `deploy/deploy_all.py` on Windows (requires Administrator for symlinks) |
| `commit_submodules.py` | Commit + push all `Submodules/*` repos with a shared message, skipping clean ones |

### `deploy/`
| File | Description |
|---|---|
| `deploy_all.py` | Full local deploy: assets → manifests → symlinks → git hooks |
| `deploy_assets.py` | Copy `icon.png` and `LICENSE` from Setup root into every mod's `src/` |
| `deploy_manifests.py` | Generate `manifest.json` for every mod (reads `thunderstore.toml`) |
| `deploy_links.py` | Create r2modman profile symlinks for every mod |
| `deploy_hooks.py` | Configure `.githooks` paths for every mod repo |
| `deploy_secrets.py` | Set a GitHub Actions secret across the coordinator repo and all `Submodules/*` repos |
| `deploy_common.py` | Shared utilities: mod discovery, profile path resolution, arg parser |
| `generate_manifest.py` | Generate manifest for a single mod |

### `scaffold/`
| File | Description |
|---|---|
| `new_pack.py` | Scaffold a complete new shell repo: GitHub repos, submodules, coordinator files, initial push |
| `new_module.py` | Scaffold a new module repo from template: create on GitHub, fill identity, and register as submodule |
| `register_submodules.py` | Register untracked repos in `Submodules/` as submodules. `--prune` removes entries whose folder is gone |
| `setup_common.py` | Shared utilities for scaffold scripts: `fill`, `write`, `run`, `rmtree` |

### `migrate/`
| File | Description |
|---|---|
| `transfer_repos.py` | Transfer submodule repos from one GitHub org to another via `gh api`. Writes `repos.txt` on completion |
| `bulk_add.py` | Add submodules in bulk from a `repos.txt` file (produced by `transfer_repos.py`) |
| `rewire.py` | Update submodule URLs in `.gitmodules`, sync to `.git/config`, update each submodule's `origin` remote |

### `templates/`
File templates used by `new_pack.py` during scaffolding. Placeholders use `{{KEY}}` syntax.

| Folder | Used for |
|---|---|
| `templates/coordinator/` | Files copied into the new coordinator repo (README, etc.) |
| `templates/shell/` | Files copied into the new shell repo (.gitignore, workflows, etc.) |

---

## Workflows

### Start a new pack from scratch

Clone Setup as a standalone repo, run `new_pack.py`, and the standalone clone is replaced by a submodule automatically.

```bash
git clone https://github.com/h2-modpack/Setup
python Setup/scaffold/new_pack.py --pack-id "my-pack" --namespace mynamespace --org my-org
cd ../my-pack-modpack
python Setup/deploy/deploy_all.py
```

`new_pack.py` creates the shell repo and coordinator on GitHub, wires Lib/Framework/coordinator/Setup as submodules, and pushes the initial commit.

### Add a new module to an existing pack

```bash
python Setup/scaffold/new_module.py --name MyModName --pack-id my-pack --namespace adamant --org h2-modpack
python Setup/deploy/deploy_all.py --overwrite
```

Creates the GitHub repo from template, fills in module identity, commits, and registers it as a submodule.
Generated repos inherit the current module template contract: split `main.lua` / `data.lua` / `logic.lua` / `ui.lua`,
host-owned hook registration, and the standard module CI baseline.

### Local deploy after any change

```bash
python Setup/deploy/deploy_all.py          # first time
python Setup/deploy/deploy_all.py --overwrite   # force refresh
./Setup/lin.sh                             # shorthand on Linux
```

### Configure release secrets across a pack

Preferred one-org-per-pack setup: create these org-level secrets once, with selected-repository visibility:

- `TCLI_AUTH_TOKEN`
- `SUBMODULE_UPDATE_TOKEN`
- `RELEASE_DISPATCH_TOKEN`

Then link them to this pack's repos:

```bash
python Setup/deploy/deploy_secrets.py --link-org-secrets --dry-run
python Setup/deploy/deploy_secrets.py --link-org-secrets
```

This links:

- `TCLI_AUTH_TOKEN` to the coordinator repo and every `Submodules/*` repo
- `SUBMODULE_UPDATE_TOKEN` and `RELEASE_DISPATCH_TOKEN` to the shell repo

Lib and Framework are excluded by default because they live in the shared `h2-modpack` org. Add `--include-lib-framework` only when intentionally managing those repos from this shell.

Fallback repo-level setup is still available. To set `TCLI_AUTH_TOKEN` directly on the coordinator and every game submodule repo:

```powershell
$env:TCLI_AUTH_TOKEN = "your-thunderstore-token"
python Setup/deploy/deploy_secrets.py
```

To also set shell workflow secrets directly on the shell repo:

```powershell
$env:TCLI_AUTH_TOKEN = "your-thunderstore-token"
$env:SUBMODULE_UPDATE_TOKEN = "your-github-pr-token"
$env:RELEASE_DISPATCH_TOKEN = "your-github-dispatch-token"
python Setup/deploy/deploy_secrets.py --include-shell
```

If you do not want to put token values in environment variables, omit them and the script will prompt securely.

### Adopt existing repos as submodules

If you have repos cloned in `Submodules/` that aren't registered in `.gitmodules` yet:

```bash
python Setup/scaffold/register_submodules.py
```

Scans `Submodules/` for git repos with a remote, registers any that are missing from `.gitmodules`.

### Clean up removed modules

After deleting module folders from `Submodules/`:

```bash
python Setup/scaffold/register_submodules.py --prune
```

Runs `git submodule deinit` + `git rm` for every `.gitmodules` entry whose folder no longer exists.

### Move a pack to a different GitHub org

Transfer all repos, then re-wire the new shell to point at them:

```bash
# 1. Transfer repos on GitHub and produce repos.txt
cd old-shell
python Setup/migrate/transfer_repos.py --from-org old-org --to-org new-org

# 2. Add them to the new shell
cd ../new-shell
python Setup/migrate/bulk_add.py --repos ../old-shell/repos.txt
python Setup/deploy/deploy_all.py --overwrite

# 3. (Optional) Update the old shell to point at the new org instead of removing
cd ../old-shell
python Setup/migrate/rewire.py --from-org old-org --to-org new-org
```

### Commit a shared change across all modules

```bash
python Setup/commit_submodules.py "fix: update config schema"
```

Commits and pushes every `Submodules/*` repo that has changes. Skips clean ones.

---

## Flags

Most scripts share these flags:

| Flag | Default | Description |
|---|---|---|
| `--overwrite` | off | Overwrite existing files/links instead of skipping |
| `--profile NAME` | `h2-dev` | r2modman profile to deploy into |
| `--dry-run` | off | Show what would happen without making changes (migrate scripts) |
