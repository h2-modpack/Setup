-- Generic real-module boot smoke for shell checkouts.
-- Module-owned tests stay behavior-focused; optional smoke_env.lua files only
-- provide fake game globals needed for a real src/main.lua boot.

local scriptPath = arg and arg[0] or "ModpackTools/tests/test_module_smoke.lua"
local toolsTestDir = string.match(scriptPath, "^(.*)[/\\][^/\\]+$") or "ModpackTools/tests"
local harness = dofile(toolsTestDir .. "/module_entrypoint_harness.lua")

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

local function tryReadFile(path)
    local file = io.open(path, "r")
    if not file then
        return nil
    end
    local content = file:read("*a")
    file:close()
    return content
end

local function discoverModules()
    local modules = {}
    for _, dir in ipairs(listDirs("Submodules")) do
        local srcDir = "Submodules/" .. dir .. "/src"
        local main = tryReadFile(srcDir .. "/main.lua")
        if main then
            local packId = string.match(main, "local%s+PACK_ID%s*=%s*['\"]([^'\"]+)['\"]")
            local moduleId = string.match(main, "local%s+MODULE_ID%s*=%s*['\"]([^'\"]+)['\"]")
            if packId and moduleId then
                modules[#modules + 1] = {
                    pluginGuid = dir,
                    moduleSrcDir = srcDir,
                    packId = packId,
                    moduleId = moduleId,
                    fixturePath = "Submodules/" .. dir .. "/tests/smoke_env.lua",
                }
            end
        end
    end
    return modules
end

local function loadFixture(path)
    if not tryReadFile(path) then
        return nil
    end
    local fixture = dofile(path)
    if type(fixture) == "function" then
        return fixture
    end
    if type(fixture) == "table" and type(fixture.configureEnv) == "function" then
        return fixture.configureEnv
    end
    fail(path .. " must return a configureEnv function or table with configureEnv")
end

local function bootModule(module)
    local boot = harness.bootModule({
        pluginGuid = module.pluginGuid,
        moduleSrcDir = module.moduleSrcDir,
        configureEnv = loadFixture(module.fixturePath),
    })

    assertTruthy(boot.liveModule, module.pluginGuid .. " did not publish a live module")
    assertEquals(boot.liveModule.getOwnerId(), module.pluginGuid, module.pluginGuid .. " owner id")
    assertEquals(boot.liveModule.getModuleId(), module.moduleId, module.pluginGuid .. " module id")
    assertEquals(boot.liveModule.getPackId(), module.packId, module.pluginGuid .. " pack id")
end

local modules = discoverModules()
assertTruthy(#modules > 0, "no feature modules discovered for smoke")

for _, module in ipairs(modules) do
    bootModule(module)
end

print(string.format("%d real module smoke tests passed.", #modules))
