# {{WINDOW_TITLE}} Modpack

Shell repo for the {{WINDOW_TITLE}} modpack. Contains all module submodules, the coordinator, and the shared Framework/Lib.

## Structure

```
{{SHELL_REPO}}/
├── {{COORD_ID}}/          # Coordinator: pack identity, config, profiles
├── adamant-ModpackFramework/  # Shared UI, discovery, hash, HUD
├── adamant-ModpackLib/        # Shared utilities
├── Setup/                     # Deploy scripts
└── Submodules/                # Game modules (one repo each)
```

## Setup

```bash
git clone --recurse-submodules https://github.com/{{ORG}}/{{SHELL_REPO}}.git
python Setup/deploy/deploy_all.py
```

## Releasing

Use the **Release All** workflow (`Actions → Release All`) to publish a new version across all modules.

## Architecture

See [h2-modular-modpack](https://github.com/h2-modpack/h2-modular-modpack) for full architecture documentation (Framework, Lib, staging pattern, hash pipeline).
