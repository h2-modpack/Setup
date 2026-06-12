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
            modules[#modules + 1] = {
                pluginGuid = dir,
                moduleSrcDir = srcDir,
                mainPath = srcDir .. "/main.lua",
                fixturePath = "Submodules/" .. dir .. "/tests/smoke_env.lua",
            }
        end
    end
    return modules
end

local function loadFixture(path)
    if not tryReadFile(path) then
        return {}
    end
    local fixture = dofile(path)
    if type(fixture) == "function" then
        return { configureEnv = fixture }
    end
    if type(fixture) == "table" and type(fixture.configureEnv) == "function" then
        if fixture.expectedPackId ~= nil and type(fixture.expectedPackId) ~= "string" then
            fail(path .. " expectedPackId must be a string")
        end
        if fixture.expectedModuleId ~= nil and type(fixture.expectedModuleId) ~= "string" then
            fail(path .. " expectedModuleId must be a string")
        end
        return fixture
    end
    fail(path .. " must return a configureEnv function or table with configureEnv")
end

local function bootModule(module)
    local fixture = loadFixture(module.fixturePath)
    local ok, boot = xpcall(function()
        return harness.bootModule({
            pluginGuid = module.pluginGuid,
            moduleSrcDir = module.moduleSrcDir,
            configureEnv = fixture.configureEnv,
        })
    end, debug.traceback)

    if not ok then
        fail(string.format(
            "%s boot smoke failed: %s\nIf this module needs game globals, add or update %s",
            module.pluginGuid,
            tostring(boot),
            module.fixturePath
        ))
    end

    assertTruthy(boot.liveModule, module.pluginGuid .. " did not publish a live module")
    assertEquals(boot.liveModule.getOwnerId(), module.pluginGuid, module.pluginGuid .. " owner id")
    assertTruthy(
        type(boot.liveModule.getModuleId()) == "string" and boot.liveModule.getModuleId() ~= "",
        module.pluginGuid .. " module id"
    )
    assertTruthy(
        type(boot.liveModule.getPackId()) == "string" and boot.liveModule.getPackId() ~= "",
        module.pluginGuid .. " pack id"
    )
    if fixture.expectedModuleId then
        assertEquals(boot.liveModule.getModuleId(), fixture.expectedModuleId, module.pluginGuid .. " module id")
    end
    if fixture.expectedPackId then
        assertEquals(boot.liveModule.getPackId(), fixture.expectedPackId, module.pluginGuid .. " pack id")
    end
end

local modules = discoverModules()
assertTruthy(#modules > 0, "no feature modules discovered for smoke")

for _, module in ipairs(modules) do
    bootModule(module)
end

print(string.format("%d real module smoke tests passed.", #modules))
