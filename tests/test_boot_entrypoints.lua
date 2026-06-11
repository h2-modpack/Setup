-- Generic boot pipeline smoke for convention-following adamant modpacks.
-- This intentionally uses synthetic feature modules so pack/module-specific
-- game globals remain owned by each module's own tests.

local function fail(message)
    error(message, 2)
end

local function assertTruthy(value, message)
    if not value then
        fail(message)
    end
end

local function assertEquals(actual, expected, message)
    if actual ~= expected then
        fail(string.format("%s: expected %s, got %s", message, tostring(expected), tostring(actual)))
    end
end

local function deepCopy(value)
    if type(value) ~= "table" then
        return value
    end
    local copy = {}
    for key, child in pairs(value) do
        copy[key] = deepCopy(child)
    end
    return copy
end

local function listDirs(path)
    local isWindows = package.config:sub(1, 1) == "\\"
    local command
    if isWindows then
        command = string.format('dir /b /ad "%s" 2>nul', path)
    else
        command = string.format('find "%s" -maxdepth 1 -mindepth 1 -type d -printf "%%f\\n" 2>/dev/null', path)
    end

    local handle = io.popen(command)
    if not handle then
        return {}
    end

    local dirs = {}
    for line in handle:lines() do
        if line ~= "" then
            dirs[#dirs + 1] = line
        end
    end
    handle:close()
    table.sort(dirs)
    return dirs
end

local function readFile(path)
    local file = assert(io.open(path, "r"))
    local content = file:read("*a")
    file:close()
    return content
end

local function tryReadFile(path)
    local file = io.open(path, "r")
    if not file then
        return nil
    end
    local content = file:read("*a")
    file:close()
    return content
end

local function readTomlPackage(path)
    local content = tryReadFile(path)
    if not content then
        return nil
    end
    local namespace = string.match(content, "\nnamespace%s*=%s*['\"]([^'\"]+)['\"]")
        or string.match(content, "^namespace%s*=%s*['\"]([^'\"]+)['\"]")
    local name = string.match(content, "\nname%s*=%s*['\"]([^'\"]+)['\"]")
        or string.match(content, "^name%s*=%s*['\"]([^'\"]+)['\"]")
    if not namespace or not name then
        return nil
    end
    return {
        namespace = namespace,
        name = name,
        fullName = namespace .. "-" .. name,
    }
end

local function discoverPack()
    local cores = {}
    for _, dir in ipairs(listDirs(".")) do
        local package = readTomlPackage(dir .. "/thunderstore.toml")
        local coordinatorPackagePrefix
        if package then
            coordinatorPackagePrefix = string.match(package.name, "^(.+)_Modpack$")
        end
        if coordinatorPackagePrefix then
            cores[#cores + 1] = {
                dir = dir,
                coordinatorPackagePrefix = coordinatorPackagePrefix,
                package = package,
            }
        end
    end
    assertEquals(#cores, 1, "convention coordinator repo count")

    local core = cores[1]
    local coreMain = readFile(core.dir .. "/src/main.lua")
    local packId = string.match(coreMain, "PACK_ID%s*=%s*['\"]([^'\"]+)['\"]")
    assertTruthy(packId, "Coordinator src/main.lua must declare PACK_ID")

    local modules = {}
    for _, dir in ipairs(listDirs("Submodules")) do
        local mainPath = "Submodules/" .. dir .. "/src/main.lua"
        local main = tryReadFile(mainPath)
        local package = readTomlPackage("Submodules/" .. dir .. "/thunderstore.toml")
        local modulePackId = main and string.match(main, "PACK_ID%s*=%s*['\"]([^'\"]+)['\"]")
        if package and modulePackId == packId then
            modules[#modules + 1] = {
                dir = dir,
                id = package.name,
            }
        end
    end
    table.sort(modules, function(a, b)
        return a.id < b.id
    end)
    assertTruthy(#modules > 0, "convention feature module count")

    return {
        coreDir = core.dir,
        packId = packId,
        modules = modules,
    }
end

local function makeImgui()
    return setmetatable({}, {
        __index = function()
            return function()
                return false
            end
        end,
    })
end

local function makeConfig()
    return {
        ModEnabled = true,
        DebugMode = false,
        Profiles = {
            {
                Name = "Default",
                Hash = "",
                Tooltip = "",
            },
        },
    }
end

local function makeModUtil(callbacks, globals)
    local path = {}
    path.Context = {}

    function path.Wrap(name, handler)
        callbacks.wraps[#callbacks.wraps + 1] = { kind = "wrap", name = name, handler = handler }
    end

    function path.Override(name, replacement)
        callbacks.wraps[#callbacks.wraps + 1] = { kind = "override", name = name, replacement = replacement }
    end

    function path.Restore(name)
        callbacks.wraps[#callbacks.wraps + 1] = { kind = "restore", name = name }
    end

    function path.Context.Wrap(name, handler)
        callbacks.wraps[#callbacks.wraps + 1] = { kind = "contextWrap", name = name, handler = handler }
    end

    local runtime = {
        Path = path,
    }

    globals.ModUtil = runtime

    return {
        globals = globals,
        once_loaded = {
            game = function(callback)
                callbacks.gameLoaded[#callbacks.gameLoaded + 1] = callback
            end,
        },
        mod = runtime,
    }
end

local function resetWorld()
    local callbacks = {
        allModsLoaded = {},
        gameLoaded = {},
        wraps = {},
        imgui = {},
        alwaysDraw = {},
        menuBar = {},
        setupRunDataCount = 0,
    }
    local game = {
        DeepCopyTable = deepCopy,
        SetupRunData = function()
            callbacks.setupRunDataCount = callbacks.setupRunDataCount + 1
        end,
    }
    local modUtil = makeModUtil(callbacks, game)

    local mods = {
        ["SGG_Modding-ENVY"] = {
            auto = function()
                return {}
            end,
        },
        ["SGG_Modding-Chalk"] = {
            auto = function()
                return makeConfig()
            end,
            original = function(config)
                return config
            end,
        },
        ["SGG_Modding-ReLoad"] = {
            auto_single = function()
                return {
                    load = function(...)
                        for index = 1, select("#", ...) do
                            local callback = select(index, ...)
                            if type(callback) == "function" then
                                callback()
                            end
                        end
                    end,
                }
            end,
        },
        ["SGG_Modding-ModUtil"] = modUtil,
    }

    function mods.on_all_mods_loaded(callback)
        callbacks.allModsLoaded[#callbacks.allModsLoaded + 1] = callback
    end

    rom = {
        mods = mods,
        game = game,
        ImGui = makeImgui(),
        ImGuiCol = {
            Text = 1,
            TextDisabled = 2,
            WindowBg = 3,
            ChildBg = 4,
            Header = 5,
            HeaderHovered = 6,
            HeaderActive = 7,
            Button = 8,
            ButtonHovered = 9,
            ButtonActive = 10,
            FrameBg = 11,
            FrameBgHovered = 12,
            FrameBgActive = 13,
            CheckMark = 14,
            Tab = 15,
            TabHovered = 16,
            TabActive = 17,
            Separator = 18,
            Border = 19,
            TitleBgActive = 20,
        },
        ImGuiCond = {
            FirstUseEver = 1,
        },
        gui = {
            add_imgui = function(callback)
                callbacks.imgui[#callbacks.imgui + 1] = callback
            end,
            add_always_draw_imgui = function(callback)
                callbacks.alwaysDraw[#callbacks.alwaysDraw + 1] = callback
            end,
            add_to_menu_bar = function(callback)
                callbacks.menuBar[#callbacks.menuBar + 1] = callback
            end,
            is_open = function()
                return false
            end,
        },
    }

    game = rom.game
    modutil = modUtil
    ScreenData = {
        HUD = {
            ComponentData = {},
        },
    }

    FrameworkPackRegistry = nil
    lib = nil
    Framework = nil
    public = nil
    _PLUGIN = nil

    return callbacks
end

local function addFallback(env, fallback)
    local metatable = getmetatable(env)
    if metatable == nil then
        setmetatable(env, { __index = fallback })
    elseif metatable.__index == nil then
        metatable.__index = fallback
    end
    return env
end

local function loadPlugin(guid, srcDir, mainPath)
    local env = addFallback({
        _G = _G,
        _PLUGIN = { guid = guid },
        public = {},
    }, _G)

    env.import_as_fallback = function(source)
        if type(source) ~= "table" then
            return
        end
        for key, value in pairs(source) do
            if env[key] == nil then
                env[key] = value
            end
        end
    end

    env.import = function(path, fenv, ...)
        local chunkEnv = fenv or env
        if fenv then
            addFallback(chunkEnv, env)
        end
        local chunk = assert(loadfile(srcDir .. "/" .. path, "t", chunkEnv))
        return chunk(...)
    end

    local chunk = assert(loadfile(mainPath or (srcDir .. "/main.lua"), "t", env))
    chunk()
    rom.mods[guid] = env.public
    return env
end

local function runCallbacks(callbacks, label)
    for index, callback in ipairs(callbacks) do
        local ok, err = xpcall(callback, debug.traceback)
        if not ok then
            fail(string.format("%s callback %d failed: %s", label, index, tostring(err)))
        end
    end
end

local function loadLibAndFramework()
    local libEnv = loadPlugin("adamant-ModpackLib", "adamant-ModpackLib/src")
    local frameworkEnv = loadPlugin("adamant-ModpackFramework", "adamant-ModpackFramework/src")
    assertEquals(type(frameworkEnv.public.createPack), "function", "Framework.createPack export")
    return libEnv, frameworkEnv
end

local function installSyntheticModules(pack)
    local libApi = rom.mods["adamant-ModpackLib"]
    for _, module in ipairs(pack.modules) do
        rom.mods[module.dir] = {}
        local host = libApi.createModule({
            pluginGuid = module.dir,
            modpack = pack.packId,
            id = module.id,
            name = module.id,
        })
        host.data.define({
            { type = "bool", alias = "SmokeFlag", default = false },
        })
        host.ui.tab(function() end)
        local ok, err = host.activate()
        assertTruthy(ok, "synthetic module did not activate: " .. tostring(err))
    end
end

local function testConventionPackPipelineBoots()
    local pack = discoverPack()
    local callbacks = resetWorld()
    local _, frameworkEnv = loadLibAndFramework()

    installSyntheticModules(pack)
    loadPlugin(pack.coreDir, pack.coreDir .. "/src")

    runCallbacks(callbacks.allModsLoaded, "on_all_mods_loaded")

    runCallbacks(callbacks.gameLoaded, "once_loaded.game")
    runCallbacks(callbacks.alwaysDraw, "always_draw_imgui")

    local packRegistry = frameworkEnv.FrameworkPackRegistry
    local bootedPack = packRegistry and packRegistry.packs and packRegistry.packs[pack.packId]
    assertTruthy(bootedPack, "Core did not initialize the Framework pack")
    assertEquals(#bootedPack.moduleRegistry.modules, #pack.modules, "Framework discovered module count")

    for _, module in ipairs(pack.modules) do
        assertTruthy(bootedPack.moduleRegistry.modulesById[module.id],
            "Framework did not discover " .. module.id)
    end
end

testConventionPackPipelineBoots()

print("1 generic boot pipeline smoke test passed.")
