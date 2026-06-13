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

local function firstExistingFile(paths)
    for _, path in ipairs(paths) do
        local file = io.open(path, "r")
        if file then
            file:close()
            return path
        end
    end
    return nil
end

local function dirname(path)
    return path and path:match("^(.*)[/\\][^/\\]+$") or nil
end

local function currentScriptDir()
    local source = debug.getinfo(1, "S").source
    if type(source) == "string" and source:sub(1, 1) == "@" then
        return dirname(source:sub(2))
    end
    return "ModpackTools/tests"
end

local function resolveLibRootFromEnv()
    local envDir = os.getenv("MODPACK_LIB_DIR")
    if type(envDir) ~= "string" or envDir == "" then
        return nil
    end
    if envDir:match("[/\\]src$") then
        return dirname(envDir)
    end
    return envDir
end

local function resolveLibFakeEnginePath()
    local scriptDir = currentScriptDir()
    local envRoot = resolveLibRootFromEnv()
    local candidates = {}
    if envRoot then
        candidates[#candidates + 1] = envRoot .. "/tests/harness/fake_engine.lua"
    end
    candidates[#candidates + 1] = scriptDir .. "/../../adamant-ModpackLib/tests/harness/fake_engine.lua"
    candidates[#candidates + 1] = "adamant-ModpackLib/tests/harness/fake_engine.lua"
    candidates[#candidates + 1] = ".modpacklib/tests/harness/fake_engine.lua"
    candidates[#candidates + 1] = "../../adamant-ModpackLib/tests/harness/fake_engine.lua"

    local path = firstExistingFile(candidates)
    assert(path, "unable to locate adamant-ModpackLib/tests/harness/fake_engine.lua")
    return path
end

local fakeEngine = dofile(resolveLibFakeEnginePath())

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

local function resolveLibSrcDir()
    local scriptDir = currentScriptDir()
    local envRoot = resolveLibRootFromEnv()
    local candidates = {}
    if envRoot then
        candidates[#candidates + 1] = envRoot .. "/src"
    end
    candidates[#candidates + 1] = scriptDir .. "/../../adamant-ModpackLib/src"
    candidates[#candidates + 1] = "adamant-ModpackLib/src"
    candidates[#candidates + 1] = ".modpacklib/src"
    candidates[#candidates + 1] = "../../adamant-ModpackLib/src"

    local files = {}
    for index, path in ipairs(candidates) do
        files[index] = path .. "/main.lua"
    end

    local mainFile = firstExistingFile(files)
    assert(mainFile, "unable to locate adamant-ModpackLib/src/main.lua")
    local srcDir = mainFile:gsub("/main%.lua$", "")
    return srcDir
end

local function createWorld()
    local env, callbacks = fakeEngine.createBaseEnv({
        config = makeConfig(),
        runtimeRoot = {},
        withReload = true,
        ScreenData = {
            HUD = {
                ComponentData = {},
            },
        },
        chalkOriginal = function(config)
            return config
        end,
    })
    return {
        env = env,
        callbacks = callbacks,
    }
end

local function loadLib(world)
    local libEnv = fakeEngine.loadPlugin(world.env, "adamant-ModpackLib", resolveLibSrcDir())
    world.env.lib = libEnv.public
    world.env.rom.mods["adamant-ModpackLib"] = libEnv.public
    assertEquals(type(libEnv.public.modpack.createPack), "function", "Modpack.createPack export")
    return libEnv
end

local function installSyntheticModules(world, pack)
    local libApi = world.env.rom.mods["adamant-ModpackLib"]
    for _, module in ipairs(pack.modules) do
        world.env.rom.mods[module.dir] = {}
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
    local world = createWorld()
    local libEnv = loadLib(world)

    installSyntheticModules(world, pack)
    fakeEngine.loadPlugin(world.env, pack.coreDir, pack.coreDir .. "/src")

    fakeEngine.runAllModsLoaded(world.callbacks)
    fakeEngine.runGameLoaded(world.callbacks)
    fakeEngine.runAlwaysDraw(world.callbacks)

    local runtimeRegistry = libEnv.AdamantModpackLib_Runtime and libEnv.AdamantModpackLib_Runtime.registry
    local packRegistry = runtimeRegistry and runtimeRegistry.modpacks
    local bootedPack = packRegistry and packRegistry.packs and packRegistry.packs[pack.packId]
    assertTruthy(bootedPack, "Core did not initialize the modpack")
    assertEquals(#bootedPack.moduleRegistry.modules, #pack.modules, "Modpack discovered module count")

    for _, module in ipairs(pack.modules) do
        assertTruthy(bootedPack.moduleRegistry.modulesById[module.id],
            "Modpack did not discover " .. module.id)
    end
end

testConventionPackPipelineBoots()

print("1 generic boot pipeline smoke test passed.")
