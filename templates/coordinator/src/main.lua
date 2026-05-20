-- =============================================================================
-- {{COORD_ID}}: Modpack Coordinator
-- =============================================================================
-- luacheck: globals Framework
-- Thin coordinator: wires globals, owns config/setup, delegates everything
-- else to adamant-ModpackFramework.

local mods = rom.mods
mods['SGG_Modding-ENVY'].auto()

---@diagnostic disable: lowercase-global
rom = rom
_PLUGIN = _PLUGIN
game = rom.game
modutil = mods['SGG_Modding-ModUtil']
local chalk  = mods['SGG_Modding-Chalk']
local reload = mods['SGG_Modding-ReLoad']
---@module "adamant-ModpackFramework"
---@type AdamantModpackFramework
Framework = mods["adamant-ModpackFramework"]

local config = chalk.auto('config.lua')

local PACK_ID = "{{PACK_ID}}"
local WINDOW_TITLE = "{{WINDOW_TITLE}}"
local DEFAULT_PROFILES = {}
local FRAMEWORK_OPTS = {
    moduleOrder = {
    },
}
local frameworkInitialized = false
local rebuildInProgress = false

local function rebuildFramework()
    if rebuildInProgress or not frameworkInitialized then
        return false
    end

    assert(Framework and type(Framework.tryInit) == "function",
        "{{COORD_ID}}: adamant-ModpackFramework is not loaded")

    rebuildInProgress = true
    local ok = Framework.tryInit(PACK_ID, WINDOW_TITLE, config, #config.Profiles, DEFAULT_PROFILES, FRAMEWORK_OPTS)
    rebuildInProgress = false

    if not ok then
        return false
    end

    return true
end

mods.on_all_mods_loaded(function()
    assert(Framework and type(Framework.registerCoordinator) == "function",
        "{{COORD_ID}}: adamant-ModpackFramework is not loaded")
    Framework.registerCoordinator(PACK_ID, config, rebuildFramework)
end)

local function init()
    assert(Framework and type(Framework.tryInit) == "function",
        "{{COORD_ID}}: adamant-ModpackFramework is not loaded")
    local ok = Framework.tryInit(PACK_ID, WINDOW_TITLE, config, #config.Profiles, DEFAULT_PROFILES, FRAMEWORK_OPTS)
    frameworkInitialized = ok == true
end

local loader = reload.auto_single()

local function registerGui()
    assert(Framework and type(Framework.createGuiCallbacks) == "function",
        "{{COORD_ID}}: adamant-ModpackFramework is not loaded")
    local callbacks = Framework.createGuiCallbacks(PACK_ID)
    rom.gui.add_imgui(callbacks.render)
    rom.gui.add_always_draw_imgui(callbacks.alwaysDraw)
    rom.gui.add_to_menu_bar(callbacks.menuBar)
end

modutil.once_loaded.game(function()
    loader.load(registerGui, init)
end)
