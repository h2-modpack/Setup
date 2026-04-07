# Contributing to {{COORD_ID}}

Thin coordinator for the {{WINDOW_TITLE}} modpack. Owns pack identity, config, and default profiles — delegates all orchestration to `adamant-ModpackFramework`.

## Architecture

```
src/
  main.lua    -- ENVY wiring, config, def, Framework.init call
config.lua    -- Chalk config schema (ModEnabled, DebugMode, Profiles)
```

The coordinator has no other source files. All discovery, hashing, HUD, and UI logic lives in Framework.

Use these docs as the coordinator contract:
- [Framework README.md](https://github.com/h2-modpack/adamant-ModpackFramework/blob/main/README.md)
- [Lib README.md](https://github.com/h2-modpack/adamant-ModpackLib/blob/main/README.md) for the module-side contract the coordinator expects

## What the coordinator owns

**`packId`** — `"{{PACK_ID}}"`. Discovery filter: only modules with `definition.modpack = "{{PACK_ID}}"` are picked up by Framework.

**`windowTitle`** — `"{{WINDOW_TITLE}}"`. Displayed as the ImGui window title.

**`def.defaultProfiles`** — Shipped presets. To add or update a preset, edit `def` in `src/main.lua`. Get the hash string from the Profiles tab export field in-game.

**`config.lua`** — Chalk schema: `ModEnabled`, `DebugMode`, `Profiles` array. The Profiles array length determines `def.NUM_PROFILES` and must match the number of slots rendered in the UI.

## No tests

Tests live in `adamant-ModpackFramework`. Run them from there:

```bash
cd adamant-ModpackFramework
lua5.2 tests/all.lua
```
