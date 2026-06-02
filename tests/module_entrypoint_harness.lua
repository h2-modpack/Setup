local Harness = {}

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

local function makeBitBinaryOp(predicate)
    return function(a, b)
        local result = 0
        local bitValue = 1
        a = a or 0
        b = b or 0

        while a > 0 or b > 0 do
            local abit = a % 2
            local bbit = b % 2
            if predicate(abit, bbit) then
                result = result + bitValue
            end
            a = math.floor(a / 2)
            b = math.floor(b / 2)
            bitValue = bitValue * 2
        end

        return result
    end
end

local function installBit32Fallback(env)
    if env.bit32 ~= nil then
        return
    end
    env.bit32 = {
        band = makeBitBinaryOp(function(a, b)
            return a == 1 and b == 1
        end),
        bor = makeBitBinaryOp(function(a, b)
            return a == 1 or b == 1
        end),
        bnot = function(a)
            return 4294967295 - (a or 0)
        end,
        lshift = function(a, n)
            return ((a or 0) * (2 ^ (n or 0))) % (2 ^ 32)
        end,
        rshift = function(a, n)
            return math.floor((a or 0) / (2 ^ (n or 0)))
        end,
    }
end

function Harness.makeColorTable()
    return setmetatable({
        Black = { 0, 0, 0, 255 },
    }, {
        __index = function(colors, key)
            local color = { 255, 255, 255, 255 }
            rawset(colors, key, color)
            return color
        end,
    })
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
        DebugMode = false,
    }
end

local function makeModUtil(callbacks, env)
    local path = {}
    path.Context = {}

    function path.Wrap(name, handler)
        callbacks.wraps[#callbacks.wraps + 1] = { kind = "wrap", name = name, handler = handler }
        local base = env[name]
        env[name] = function(...)
            return handler(base or function() end, ...)
        end
    end

    function path.Override(name, replacement)
        callbacks.wraps[#callbacks.wraps + 1] = { kind = "override", name = name, replacement = replacement }
        env[name] = replacement
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

    return {
        globals = env,
        once_loaded = {
            game = function(callback)
                callbacks.gameLoaded[#callbacks.gameLoaded + 1] = callback
            end,
        },
        mod = runtime,
    }
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

local function createBaseEnv()
    local env = addFallback({}, _G)
    env._G = env
    env.public = nil
    env._PLUGIN = nil
    env.FrameworkPackRegistry = false
    installBit32Fallback(env)

    local callbacks = {
        gameLoaded = {},
        wraps = {},
        imgui = {},
        alwaysDraw = {},
        menuBar = {},
        setupRunDataCount = 0,
    }
    local modUtil = makeModUtil(callbacks, env)
    env.ModUtil = modUtil.mod

    env.rom = {
        mods = {},
        game = {
            DeepCopyTable = deepCopy,
            SetupRunData = function()
                callbacks.setupRunDataCount = callbacks.setupRunDataCount + 1
            end,
        },
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
    env.game = env.rom.game
    env.modutil = modUtil

    env.rom.mods["SGG_Modding-ENVY"] = {
        auto = function()
            return {}
        end,
    }
    env.rom.mods["SGG_Modding-Chalk"] = {
        auto = function()
            return makeConfig()
        end,
        original = function(config)
            return config
        end,
    }
    env.rom.mods["SGG_Modding-ReLoad"] = {
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
    }
    env.rom.mods["SGG_Modding-ModUtil"] = modUtil

    return env, callbacks
end

local function loadPlugin(baseEnv, guid, srcDir)
    local env = addFallback({
        _G = nil,
        _PLUGIN = { guid = guid },
        public = {},
        rom = baseEnv.rom,
        game = baseEnv.game,
        modutil = baseEnv.modutil,
    }, baseEnv)
    env._G = env

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

    local chunk = assert(loadfile(srcDir .. "/main.lua", "t", env))
    chunk()
    baseEnv.rom.mods[guid] = env.public
    return env
end

local function runGameLoaded(callbacks)
    for index, callback in ipairs(callbacks.gameLoaded) do
        local ok, err = xpcall(callback, debug.traceback)
        if not ok then
            error(string.format("once_loaded.game callback %d failed: %s", index, tostring(err)), 2)
        end
    end
end

function Harness.bootModule(opts)
    assert(type(opts) == "table", "bootModule opts are required")
    assert(type(opts.pluginGuid) == "string", "bootModule pluginGuid is required")
    assert(type(opts.moduleSrcDir) == "string", "bootModule moduleSrcDir is required")

    local env, callbacks = createBaseEnv()
    if type(opts.configureEnv) == "function" then
        opts.configureEnv(env)
    end

    local libEnv = loadPlugin(env, "adamant-ModpackLib", opts.libSrcDir or "../../adamant-ModpackLib/src")
    env.lib = libEnv.public
    env.rom.mods["adamant-ModpackLib"] = env.lib

    local moduleEnv = loadPlugin(env, opts.pluginGuid, opts.moduleSrcDir)
    runGameLoaded(callbacks)

    local frameworkRuntime = env.lib.createFrameworkRuntime("adamant-ModpackFramework")

    return {
        env = env,
        lib = env.lib,
        moduleEnv = moduleEnv,
        callbacks = callbacks,
        liveModule = frameworkRuntime.modules.getLiveModule(opts.pluginGuid),
    }
end

return Harness
