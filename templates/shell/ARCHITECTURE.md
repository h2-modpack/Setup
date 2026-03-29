# h2-modpack - Architecture Overview

## What this system is

A modular modpack system for Hades 2. Each module lives in its own repository and can be installed standalone, but when a coordinator is present it discovers all installed modules automatically, hosts them in a shared window, and manages their configuration as a single shareable hash.

The design goal is zero coupling between modules: a module author writes their logic, declares a definition table, and the rest is handled for them.

---

## Layer overview

| Layer | Repo | Role |
|---|---|---|
| Coordinator | `adamant-ModpackXXXXCore` | Owns `packId`, `windowTitle`, `defaultProfiles`, `config.lua`. Delegates orchestration to Framework. |
| Framework | `adamant-ModpackFramework` | Discovery, hash, HUD, shared UI. Exposes `Framework.init(params)`. |
| Lib | `adamant-ModpackLib` | Shared utilities, field types, managed special-state helpers, standalone helpers. |
| Modules | `Submodules/adamant-*` | Standalone mods. Opt into the pack via `public.definition.modpack = packId`. |

---

## Components

### Coordinator (`adamant-ModpackXXXXCore`)

About 50 lines. Owns only pack identity, coordinator config, and default profiles. Registers GUI callbacks once and delegates runtime setup to Framework:

```lua
local PACK_ID = "speedrun"

modutil.once_loaded.game(function()
    local Framework = mods["adamant-ModpackFramework"]
    rom.gui.add_imgui(Framework.getRenderer(PACK_ID))
    rom.gui.add_to_menu_bar(Framework.getMenuBar(PACK_ID))
    loader.load(init, init)
end)
```

Framework never calls `rom.gui.add_imgui` directly; the coordinator owns GUI registration.

### Framework (`adamant-ModpackFramework`)

Reusable orchestration library. Coordinator calls `Framework.init(params)` and gets everything else for free.

```text
src/
  main.lua        -- Framework table, ENVY wiring, Framework.init, public API
  discovery.lua   -- createDiscovery(packId, config, lib)
  hash.lua        -- createHash(discovery, config, lib, packId)
  ui_theme.lua    -- createTheme()
  hud.lua         -- createHud(packId, packIndex, hash, theme, config, modutil)
  ui.lua          -- createUI(discovery, hud, theme, def, config, lib, packId, windowTitle)
```

Public API:
- `Framework.init(params)` - initialize or reinitialize a coordinator
- `Framework.getRenderer(packId)` - stable late-binding imgui callback
- `Framework.getMenuBar(packId)` - stable late-binding menu bar callback

Critical detail: Framework exposes API via `public.init = Framework.init` rather than `public = Framework`. ENVY holds a reference to the original `public` table.

### Lib (`adamant-ModpackLib`)

Shared infrastructure, accessed by every module as `rom.mods["adamant-ModpackLib"]`. Provides:
- `createBackupSystem()` - deep-copy backup and restore of game data tables
- `createSpecialState()` - builds a managed `specialState` object from a `stateSchema`
- `isEnabled(config, packId)` - checks a module's own `Enabled` flag and the coordinator's master toggle when present
- `warn(packId, enabled, msg)` - framework diagnostic print
- `log(name, enabled, msg)` - per-module trace print
- `validateSchema(schema, label)` - checks field descriptors at declaration time
- `drawField(ui, field, value, width)` - renders regular-module option widgets
- `captureSpecialConfigSnapshot(...)` / `warnIfSpecialConfigBypassedState(...)` - debug helpers for special-module UI misuse detection

Lib has no knowledge of Framework or the coordinator. Any module can use it standalone.

### Individual modules

Each module is its own mod package. It declares a `definition` table and implements gameplay logic. Framework discovers it automatically; modules do not register themselves.

### External dependencies

- Chalk - config file persistence (`config.lua` per mod)
- ENVY - wires engine globals (`rom`, `public`, `_PLUGIN`) into the mod scope
- ModUtil - function wrapping (`Path.Wrap`) for hooking game functions
- ReLoad - hot reload support (`auto_single()`)

---

## Module lifecycle

```text
Game starts
  -> each module file loads
     -> wires globals via ENVY
     -> declares public.definition
     -> builds stateSchema (special modules)
     -> schedules modutil.once_loaded.game(...)

Game data loads
  -> Framework runs discovery (scans rom.mods for modpack = packId)
  -> each module loader fires
     -> import_as_fallback(rom.game)
     -> registerHooks()
     -> if enabled: apply()

Player is in game
  -> hooks fire on game events
  -> Framework renders the shared UI each frame
     -> reads Framework-owned staging for regular modules
     -> passes public.specialState to special modules
     -> if a special marked itself dirty during draw:
        -> flush to config
        -> invalidate cached hash
        -> update HUD

Hash / profiles
  -> Framework computes hash from current configs
  -> HUD fingerprint updates when config changes
```

---

## Regular modules vs special modules

### Regular module

A module with a simple on/off state and optional inline options. Framework renders its row and option controls.

Config shape: `config.Enabled` plus flat option keys such as `config.Mode` or `config.Strict`.

### Special module

A module with complex or structured configuration that deserves its own sidebar tab. It owns its UI and declares a `stateSchema` so Framework can hash its state.

Config shape: `config.Enabled` plus arbitrarily nested config such as `config.FirstHammers.WeaponAxe`.

Use a special module when:
- the configuration is structured, not a flat list of toggles
- the module benefits from a dedicated tab with custom layout
- the module needs nested config keys in the hash

---

## State and staging model

Chalk reads and writes config files on disk. That I/O is acceptable at load time or on explicit change boundaries, but not in a 60 fps render loop.

### Regular modules

Framework keeps its own staging cache for:
- coordinator `ModEnabled`
- module enabled states
- inline option values
- debug flags
- profile editing state

### Special modules

Special modules use a managed `public.specialState` object created by:

```lua
public.specialState = lib.createSpecialState(config, public.definition.stateSchema)
```

`specialState` owns a private staging table and exposes:
- `specialState.view` - read-only view used during rendering
- `specialState.get(path)` - read a value
- `specialState.set(path, value)` - write a value and mark dirty
- `specialState.update(path, fn)` - transform a value and mark dirty
- `specialState.toggle(path)` - convenience boolean toggle
- `specialState.reloadFromConfig()` - rebuild managed state from config
- `specialState.flushToConfig()` - write managed state back to config
- `specialState.isDirty()` - true if the module changed managed state during draw

Special modules must read from `specialState.view` and mutate schema-backed state only through `specialState.set/update/toggle`.

Framework owns the hosted flush boundary:
- before draw, it may snapshot config for debug checks
- after draw, if `specialState.isDirty()` is true, it calls `specialState.flushToConfig()`
- it then invalidates the cached hash and updates the HUD

Standalone special windows use the same `specialState` object and flush after draw in their own render path.

In debug mode, hosted and standalone special-module paths can warn if a module writes schema-backed `config` values directly during draw instead of going through `public.specialState`.

---

## Hash and profile pipeline

### Canonical string

Framework walks all discovered modules and specials and collects every value that differs from its declared default:

```text
_v=1|ModId=1|ModId.OptionKey=value|adamant-SpecialMod.configKey=value
```

- `ModId=1` / `ModId=0` - module enabled state (omitted if at default)
- `ModId.OptionKey=value` - inline option value (omitted if at default)
- `adamant-SpecialMod.configKey=value` - special-module field (omitted if at default)
- keys are sorted alphabetically for stable output
- all-defaults produces `_v=1`

The format is key-value, not positional. Adding or removing modules does not corrupt existing hashes.

### Fingerprint

A dual-pass djb2 checksum of the canonical string, base62-encoded to a fixed 12-character string. It is only a visual confirmation token shown in the HUD.

### Applying a hash

`ApplyConfigHash` parses the canonical string. For each module or field:
- if a key is present, apply that value
- if absent, reset to the declared default
- unknown keys are ignored
- `_v` must be present or the hash is rejected

After applying a hash, Framework re-snapshots its regular-module staging and calls `specialState.reloadFromConfig()` for special modules.

### Profiles

Named slots stored in the coordinator config contain:
- canonical hash string
- display name
- tooltip

Saving captures the current canonical string. Loading applies the hash and refreshes staging.

---

## Theme contract

Framework passes a `theme` table to `DrawTab(ui, specialState, theme)` and `DrawQuickContent(ui, specialState, theme)`. This table contains:
- `theme.colors`
- `theme.FIELD_MEDIUM / FIELD_NARROW / FIELD_WIDE`
- `theme.ImGuiTreeNodeFlags`
- `theme.PushTheme() / PopTheme()`

Theme does not provide text-color helper functions. Modules call ImGui directly.

Label column offset is module-specific. Each module declares its own layout constants.

---

## File map

```text
h2-modular-modpack/
  adamant-ModpackShowcaseCore/
    src/main.lua
    src/config.lua
  adamant-ModpackFramework/
    src/main.lua
    src/discovery.lua
    src/hash.lua
    src/hud.lua
    src/ui.lua
    src/ui_theme.lua
    tests/
  adamant-ModpackLib/
    src/main.lua
    tests/
  Setup/
    deploy/
    scaffold/
    migrate/
    templates/
  Submodules/adamant-*/

adamant-FirstHammer/
  src/main.lua
  config.lua

h2-modpack-template/
  src/main.lua
  src/main_special.lua
```
