-- =============================================================================
-- {{COORD_ID}}: Modpack Coordinator
-- =============================================================================
-- Thin coordinator: wires globals, owns config and def, delegates everything
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

local config = chalk.auto('config.lua')

local def = {
    NUM_PROFILES    = #config.Profiles,
    defaultProfiles = {},
}

local PACK_ID = "{{PACK_ID}}"

local function init()
    local Framework = rom.mods["adamant-ModpackFramework"]
    assert(Framework and type(Framework.init) == "function",
        "{{COORD_ID}}: adamant-ModpackFramework is not loaded")

    Framework.init({
        packId      = PACK_ID,
        windowTitle = "{{WINDOW_TITLE}}",
        config      = config,
        def         = def,
    })
end

local loader = reload.auto_single()

local function registerGui()
    local Framework = rom.mods["adamant-ModpackFramework"]
    assert(Framework and type(Framework.getRenderer) == "function",
        "{{COORD_ID}}: adamant-ModpackFramework is not loaded")

    rom.gui.add_imgui(Framework.getRenderer(PACK_ID))
    rom.gui.add_always_draw_imgui(Framework.getAlwaysDrawRenderer(PACK_ID))
    rom.gui.add_to_menu_bar(Framework.getMenuBar(PACK_ID))
end

modutil.once_loaded.game(function()
    loader.load(registerGui, init)
end)
