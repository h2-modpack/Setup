# Contributing to {{COORD_ID}}

Thin coordinator for the {{WINDOW_TITLE}} modpack. Owns pack identity, config, default profiles, coordinator registration, and Framework re-entry. It delegates discovery, hashing, HUD, and UI orchestration to `adamant-ModpackFramework`.

## Architecture

```text
src/
  main.lua    -- ENVY wiring, config, Framework params, coordinator beacon, Framework.init call
config.lua    -- Chalk config schema (ModEnabled, DebugMode, Profiles)
```

The coordinator has no other source files. All discovery, hashing, HUD, and UI logic lives in Framework.

Use these docs as the coordinator contract:

- [Framework README.md](https://github.com/h2-modpack/adamant-ModpackFramework/blob/main/README.md)
- [Lib README.md](https://github.com/h2-modpack/adamant-ModpackLib/blob/main/README.md)
- [Lib Hot Reload Architecture](https://github.com/h2-modpack/adamant-ModpackLib/blob/main/docs/HOT_RELOAD_ARCHITECTURE.md)
- [Known Limitations](https://github.com/h2-modpack/adamant-ModpackLib/blob/main/docs/KNOWN_LIMITATIONS.md)

## What the Coordinator Owns

`packId`: `"{{PACK_ID}}"`. Discovery filter: only modules with `definition.modpack = "{{PACK_ID}}"` are picked up by Framework.

`windowTitle`: `"{{WINDOW_TITLE}}"`. Displayed as the ImGui window title.

`frameworkDef.defaultProfiles`: shipped presets. To add or update a preset, edit `frameworkDef` in `src/main.lua`. Get the hash string from the Profiles tab export field in game.

`frameworkDef.moduleOrder`: optional module tab ordering by `definition.id`. Modules not listed still appear after listed modules.

`config.lua`: Chalk schema containing `ModEnabled`, `DebugMode`, and `Profiles`. The Profiles array length determines `frameworkDef.NUM_PROFILES` and must match the number of slots rendered in the UI.

Coordinator registration: `mods.on_all_mods_loaded(...)` intentionally registers the pack with Lib after the mod graph loads. ROM replays that callback on Core hot reload after the all-mods-loaded milestone, so Lib's stored rebuild callback closure stays current.

## Validation

The coordinator has no local test suite. Validate source shape with:

```bash
luacheck src/
find src -type f -name '*.lua' -print0 | xargs -0 -r -n1 luac5.2 -p
```

Framework and Lib tests live in their respective repositories.
