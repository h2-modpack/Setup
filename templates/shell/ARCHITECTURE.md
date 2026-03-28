# h2-modpack — Architecture Overview

## What this system is

A modular modpack system for Hades 2. Each module lives in its own repository and can be installed standalone, but when a coordinator is present it discovers all installed modules automatically, hosts them in a shared window, and manages their configuration as a single shareable hash.

The design goal is zero coupling between modules: a module author writes their logic, declares a definition table, and the rest is handled for them.

---

## Layer overview

| Layer | Repo | Role |
|---|---|---|
| Coordinator | `adamant-ModpackXXXXCore` | Owns: packId, windowTitle, defaultProfiles, config.lua. Delegates everything else to Framework. |
| Framework | `adamant-ModpackFramework` | Reusable library: discovery, hash, HUD, UI. Exposes `Framework.init(params)`. |
| Lib | `adamant-ModpackLib` | Shared utilities used by Framework and standalone modules. |
| Modules | `Submodules/adamant-*` | Standalone mods. Opt into the pack via `public.definition.modpack = packId`. |

---

## Components

### Coordinator (`adamant-ModpackXXXXCore`)
~50 lines. Owns only: `packId`, `windowTitle`, `defaultProfiles`, `config.lua` schema. Registers GUI callbacks once in `modutil.once_loaded.game` and delegates all orchestration to Framework:

```lua
local PACK_ID = "speedrun"

modutil.once_loaded.game(function()
    local Framework = mods['adamant-ModpackFramework']
    rom.gui.add_imgui(Framework.getRenderer(PACK_ID))
    rom.gui.add_to_menu_bar(Framework.getMenuBar(PACK_ID))
    loader.load(init, init)
end)
```

Framework never calls `rom.gui.add_imgui` directly — the coordinator owns GUI registration.

### Framework (`adamant-ModpackFramework`)
Reusable library. Coordinator calls `Framework.init(params)` and gets everything for free.

```
src/
  main.lua        -- Framework table, ENVY wiring, Framework.init, public API
  discovery.lua   -- createDiscovery(packId, config, lib)
  hash.lua        -- createHash(discovery, config, lib, packId)
  ui_theme.lua    -- createTheme()
  hud.lua         -- createHud(packId, packIndex, hash, theme, config, modutil)
  ui.lua          -- createUI(discovery, hud, theme, def, config, lib, packId, windowTitle)
```

Public API:
- `Framework.init(params)` — initialize or reinitialize a coordinator
- `Framework.getRenderer(packId)` — stable late-binding imgui callback
- `Framework.getMenuBar(packId)` — stable late-binding menu bar callback

**Critical**: Framework exposes API via `public.init = Framework.init` (not `public = Framework`). ENVY holds a reference to the original `public` table — reassigning the variable doesn't work.

### Lib (`adamant-ModpackLib`)
Shared infrastructure, accessed by every module as `rom.mods['adamant-ModpackLib']`. Provides:
- `createBackupSystem()` — deep-copy backup and restore of game data tables
- `createSpecialState()` — builds a staging table + snapshot/sync functions from a stateSchema
- `isEnabled(config, packId)` — checks a module's own `Enabled` flag AND the coordinator's master toggle when present
- `warn(msg)` — framework diagnostic, gated on `lib.config.DebugMode`
- `log(name, enabled, msg)` — per-module trace, gated on the caller's own `config.DebugMode`
- `validateSchema(schema, label)` — checks a stateSchema at declaration time, warns on bad fields
- `drawField(ui, field, value, width)` — renders a widget for a given field descriptor type (`checkbox`, `dropdown`, `radio`). If `field.tooltip` is set, a hover tooltip is shown on the label.

Lib has no knowledge of Framework or the coordinator. Any module can use it standalone.

### Individual modules
Each module is its own mod package. It declares a `definition` table and implements logic. It depends on Lib but is otherwise self-contained. Framework discovers it; modules do not register themselves.

### External dependencies
- **Chalk** — config file persistence (`config.lua` per mod). Slow I/O, not used in the render loop.
- **ENVY** — wires engine globals (`rom`, `public`, `_PLUGIN`) into the mod's scope.
- **ModUtil** — function wrapping (`Path.Wrap`) for hooking game functions.
- **ReLoad** — hot reload support (`auto_single()`).

---

## Module lifecycle

```
Game starts
  └─ each module file loads
       ├─ wires globals via ENVY
       ├─ declares public.definition
       ├─ builds stateSchema (special modules)
       └─ schedules modutil.once_loaded.game(...)

Game data loads
  ├─ Framework runs discovery (scans rom.mods for modpack = packId)
  └─ each module's loader fires:
       ├─ import_as_fallback(rom.game)   ← makes game globals available
       ├─ registerHooks()                ← wraps game functions via ModUtil
       └─ if enabled: apply()            ← mutates game data / sets initial state

Player is in game
  ├─ hooks fire on game events (SetTraitsOnLoot, StartNewRun, etc.)
  └─ Framework renders its UI window each frame:
       ├─ reads staging (plain Lua table — fast)
       ├─ calls module.DrawTab / DrawQuickContent for special modules
       └─ on user interaction → onChanged() → SyncToConfig() → Chalk write

Hash / profiles
  ├─ Framework computes hash from all current configs
  └─ HUD fingerprint updates on room transition
```

---

## Regular modules vs special modules

### Regular module
A module that has a simple on/off state and optional inline options (dropdowns, checkboxes). Framework renders its row in the module list and optionally an options panel. The module author only writes game logic.

Config shape: `config.Enabled` plus flat option keys (`config.Mode`, `config.Strict`, etc.).

### Special module
A module with complex, structured configuration that deserves its own sidebar tab. It owns its own UI entirely and declares a `stateSchema` so Framework can hash its state.

Config shape: `config.Enabled` plus arbitrarily nested data (e.g. `config.FirstHammers.WeaponAxe`).

**Use a special module when:**
- The configuration is a structured data set, not a flat list of toggles
- The module benefits from a dedicated tab with custom layout
- You need nested config keys in the hash

---

## The staging pattern

Chalk reads and writes config files on disk. That I/O is acceptable at load time or on explicit user action, but not in a 60 fps render loop.

Every module that has UI keeps a **staging table** — a plain Lua table that mirrors the Chalk config. The render loop reads and writes staging exclusively. Chalk is only touched in two controlled moments:

- **`SnapshotStaging()`** — re-reads Chalk into staging. Called at init, after a profile load, and after hot reload.
- **`SyncToConfig()`** — flushes staging into Chalk. Called by `onChanged()` after any user interaction that modifies state.

For special modules, `lib.createSpecialState(config, stateSchema)` builds the staging table and returns both functions automatically.

---

## The hash and profile pipeline

### Canonical string (the shareable hash)
Framework walks all discovered modules and specials and collects every value that differs from its declared default:

```
_v=1|ModId=1|ModId.OptionKey=value|adamant-SpecialMod.configKey=value
```

- `ModId=1` / `ModId=0` — module enabled state (omitted if at default)
- `ModId.OptionKey=value` — inline option value (omitted if at default)
- `adamant-SpecialMod.configKey=value` — special module field (omitted if at default)
- Keys are sorted alphabetically for stable output
- All-defaults produces `_v=1` (version token only)

The format is key-value, not positional. Adding or removing modules does not corrupt existing hashes.

### Fingerprint
A dual-pass djb2 checksum of the canonical string, base62-encoded to a fixed 12-character string. Displayed in the HUD as a visual confirmation that two setups match. Not decodable — it is only used for at-a-glance comparison.

### Applying a hash
`ApplyConfigHash` parses the canonical string. For each module/field: if a key is present in the hash, apply that value; if absent, reset to the declared default. Unknown keys are ignored (forward compatibility). The version token `_v` must be present or the hash is rejected.

### Profiles
Named slots (stored in the coordinator's own config) each containing a canonical hash string, a display name, and a tooltip. Saving captures the current hash. Loading calls `ApplyConfigHash` then re-snapshots all staging tables.

---

## The theme contract

Framework passes a `theme` table to `DrawTab(ui, onChanged, theme)` and `DrawQuickContent(ui, onChanged, theme)`. This table contains:

- `theme.colors` — the full color palette (`info`, `success`, `error`, `warning`, `text`, `textDisabled`, and all widget background colors)
- `theme.FIELD_MEDIUM / FIELD_NARROW / FIELD_WIDE` — layout proportions as fraction of window width
- `theme.ImGuiTreeNodeFlags` — flag constants (`DefaultOpen`, `Leaf`, `Framed`, `CollapsingHeader`, ...)
- `theme.PushTheme() / PopTheme()` — apply or remove the full color theme (useful for standalone windows)

Theme does **not** provide text-color helper functions. Modules call ImGui directly:

```lua
ui.TextColored(r, g, b, a, text)
ui.TextDisabled(text)

local headerColor = (colors and colors.info) or {1, 1, 1, 1}
ui.PushStyleColor(ImGuiCol.Text, table.unpack(headerColor))
local open = ui.CollapsingHeader("Section")
ui.PopStyleColor()
```

Label column offset is not in theme — it is module-specific. Each module declares its own `DEFAULT_LABEL_OFFSET`.

---

## File map

```
h2-modular-modpack/                    -- reference shell repo
  adamant-ModpackShowcaseCore/         -- example coordinator (~50 lines)
    src/main.lua                       -- ENVY wiring, config, def, Framework.init call
    src/config.lua                     -- Chalk config schema
  adamant-ModpackFramework/            -- reusable library
    src/main.lua                       -- Framework table, public API
    src/discovery.lua                  -- module discovery
    src/hash.lua                       -- hash encode/decode/apply
    src/hud.lua                        -- HUD fingerprint injection
    src/ui.lua                         -- full ImGui window
    src/ui_theme.lua                   -- color palette, layout constants
    tests/                             -- LuaUnit tests (hash round-trips, fingerprint stability)
  adamant-ModpackLib/                  -- shared utilities
    src/main.lua                       -- all lib utilities (one file)
    tests/                             -- LuaUnit tests (field types, backup, state mgmt)
  Setup/                               -- deploy + scaffold scripts
    deploy/                            -- local deployment scripts
    scaffold/                          -- new_pack.py, new_module.py, register_submodules.py (also syncs Core thunderstore.toml deps)
    migrate/                           -- transfer_repos.py, rewire.py, bulk_add.py
    templates/                         -- file templates for scaffolding
  Submodules/adamant-*/                -- standalone modules (each its own repo)

adamant-FirstHammer/  (example special module)
  src/main.lua                         -- definition, data tables, hooks, DrawTab, DrawQuickContent
  config.lua                           -- default config (Chalk reads this)

h2-modpack-template/                   -- starting point for new modules
  src/main.lua                         -- regular module template
  src/main_special.lua                 -- special module template
```
