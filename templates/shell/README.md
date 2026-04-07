# {{WINDOW_TITLE}} Modpack

Shell repo for the {{WINDOW_TITLE}} modpack. Contains the coordinator, shared Lib/Framework submodules, and the game-module submodules for this pack.

## Structure

```text
{{SHELL_REPO}}/
|- {{COORD_ID}}/              # Coordinator: pack identity, config, profiles
|- adamant-ModpackFramework/  # Shared UI, discovery, hash, HUD
|- adamant-ModpackLib/        # Shared utilities
|- Setup/                     # Deploy scripts
'- Submodules/                # Game modules (one repo each)
```

## Setup

```bash
git clone --recurse-submodules https://github.com/{{ORG}}/{{SHELL_REPO}}.git
python Setup/deploy/deploy_all.py
```

## Releasing

Use the **Release All** workflow (`Actions -> Release All`) to publish a new version across all modules.

## Shared Docs

Use the stable repo-root entrypoints for shared docs:

- [ModpackFramework README.md](https://github.com/h2-modpack/adamant-ModpackFramework/blob/main/README.md)
- [ModpackLib README.md](https://github.com/h2-modpack/adamant-ModpackLib/blob/main/README.md)

This shell repo should only document pack-specific structure and composition.
