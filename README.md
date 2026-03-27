# Setup

Deployment and scaffolding scripts for h2-modpack shell repos.
This is a standalone submodule — shell repos reference it at `Setup/`.

## Scaffold a new pack

Clone Setup next to where you want the new pack, then run `new_pack.py`:

```bash
git clone https://github.com/h2-modpack/Setup
python Setup/scaffold/new_pack.py --pack-id "my-pack" --namespace mynamespace --title "My Pack"
```

The new shell repo is created as a sibling of the Setup folder.
The standalone Setup clone is removed at the end — it re-enters as a submodule.

```bash
# After scaffolding:
cd ../my-pack-modpack
python Setup/deploy/deploy_all.py
```

Optional flags for `new_pack.py`:

| Flag | Default | Description |
|---|---|---|
| `--pack-id` | *(required)* | Pack identifier (e.g. `run-director`) |
| `--namespace` | *(required)* | Thunderstore namespace |
| `--title` | Title-case of pack-id | Display name |
| `--org` | `h2-modpack` | GitHub org |

## Add a module to an existing pack

```bash
python Setup/scaffold/new_module.py --name MyModName --pack-id my-pack
```

| Flag | Default | Description |
|---|---|---|
| `--name` | *(required)* | PascalCase module name |
| `--pack-id` | *(required)* | Pack this module belongs to |
| `--namespace` | `adamant` | Thunderstore namespace |
| `--org` | `h2-modpack` | GitHub org |

## Register existing repos as submodules

```bash
python Setup/scaffold/register_submodules.py
```

Scans `Submodules/` for git repos not yet in `.gitmodules` and registers them.

## Local deployment

All deploy scripts accept `--overwrite` and `--profile NAME` (default: `h2-dev`).

```bash
python Setup/deploy/deploy_all.py                    # full deploy (assets + manifests + symlinks + hooks)
python Setup/deploy/deploy_links.py                  # symlinks only
python Setup/deploy/deploy_manifests.py --overwrite  # regenerate all manifests
python Setup/deploy/deploy_assets.py                 # copy icon.png + LICENSE to all mods
python Setup/deploy/deploy_hooks.py                  # configure git hooks
```

## Other scripts

| Script | Description |
|---|---|
| `deploy/generate_manifest.py` | Generate a single mod's manifest |
| `commit_submodules.py "msg"` | Commit + push all `Submodules/*` with a shared message |
