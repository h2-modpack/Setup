local Harness = {}

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

local function resolveLibHarnessPath()
    local scriptDir = currentScriptDir()
    local envRoot = resolveLibRootFromEnv()
    local candidates = {}
    if envRoot then
        candidates[#candidates + 1] = envRoot .. "/tests/harness/plugin_boot_harness.lua"
    end
    candidates[#candidates + 1] = scriptDir .. "/../../adamant-ModpackLib/tests/harness/plugin_boot_harness.lua"
    candidates[#candidates + 1] = "adamant-ModpackLib/tests/harness/plugin_boot_harness.lua"
    candidates[#candidates + 1] = ".modpacklib/tests/harness/plugin_boot_harness.lua"
    candidates[#candidates + 1] = "../../adamant-ModpackLib/tests/harness/plugin_boot_harness.lua"

    local path = firstExistingFile(candidates)
    assert(path, "unable to locate adamant-ModpackLib/tests/harness/plugin_boot_harness.lua")
    return path
end

local function resolveLibSrcDir(override)
    if type(override) == "string" and override ~= "" then
        return override
    end

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

local libHarness = dofile(resolveLibHarnessPath())

local function copyOpts(opts)
    local copy = {}
    for key, value in pairs(opts or {}) do
        copy[key] = value
    end
    return copy
end

function Harness.boot(opts)
    local bootOpts = copyOpts(opts)
    bootOpts.libSrcDir = resolveLibSrcDir(bootOpts.libSrcDir)
    return libHarness.boot(bootOpts)
end

function Harness.bootModule(opts)
    local bootOpts = copyOpts(opts)
    bootOpts.libSrcDir = resolveLibSrcDir(bootOpts.libSrcDir)
    return libHarness.bootModule(bootOpts)
end

return Harness
