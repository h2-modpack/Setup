# {{WINDOW_TITLE}} Modpack

Shell repo for the {{WINDOW_TITLE}} modpack. Contains all module submodules, the coordinator, and the shared Framework/Lib.

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

## Architecture

Shared architecture docs live upstream:

- README: https://github.com/h2-modpack/h2-modular-modpack/blob/master/README.md
- ARCHITECTURE: https://github.com/h2-modpack/h2-modular-modpack/blob/master/ARCHITECTURE.md
