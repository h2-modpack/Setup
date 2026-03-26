# Setup

Deployment and scaffolding scripts for h2-modpack shell repos.
This is a standalone submodule — shell repos reference it at `Setup/`.

## Scaffold a new pack

Clone Setup next to where you want the new pack, then run `new_pack.py`:

```bash
git clone https://github.com/h2-modpack/Setup
python Setup/new_pack.py --pack-id "my-pack" --namespace mynamespace --title "My Pack"
```

The new shell repo is created as a sibling of the Setup folder.
The standalone Setup clone is removed at the end — it re-enters as a submodule.

```bash
# After scaffolding:
cd ../my-pack-modpack
python Setup/deploy_all.py
```

Optional flags for `new_pack.py`:

| Flag | Default | Description |
|---|---|---|
| `--pack-id` | *(required)* | Pack identifier (e.g. `run-director`) |
| `--namespace` | *(required)* | Thunderstore namespace |
| `--title` | Title-case of pack-id | Display name |
| `--name` | `<pack_id>_coordinator` | Thunderstore mod name |
| `--org` | `h2-modpack` | GitHub org for the coordinator repo |

## Local deployment

All deploy scripts accept `--overwrite` and `--profile NAME` (default: `h2-dev`).

```bash
python Setup/deploy_all.py                    # full deploy (assets + manifests + symlinks + hooks)
python Setup/deploy_links.py                  # symlinks only
python Setup/deploy_manifests.py --overwrite  # regenerate all manifests
python Setup/deploy_assets.py                 # copy icon.png + LICENSE to all mods
python Setup/deploy_hooks.py                  # configure git hooks
```

## Other scripts

| Script | Description |
|---|---|
| `generate_manifest.py` | Generate a single mod's manifest |
| `commit_submodules.py "msg"` | Commit + push all `Submodules/*` with a shared message |
