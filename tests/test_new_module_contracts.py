from __future__ import annotations

import sys
import tempfile
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
NEW_MODULE_DIR = TOOLS_DIR / "new_module"
if str(NEW_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(NEW_MODULE_DIR))

import create as create_module  # noqa: E402
from create import (  # noqa: E402
    module_repo_name,
    validate_current_lib_contract,
    validate_module_test_contract,
    parse_github_remote,
    validate_package_id,
    validate_single_line as validate_module_single_line,
    write_module_test_contract,
)


CURRENT_MAIN_LUA = """
local PLUGIN_GUID = _PLUGIN.guid

local function init()
    local module = lib.createModule({
        pluginGuid = PLUGIN_GUID,
    })
    if not module then
        return
    end

    module.data.define(data.buildStorage())
    module.ui.tab(ui.drawTab)
    module.ui.quickContent(ui.drawQuickContent)
    module.fallbackUi.attachGuiOnce(function(fallbackUi)
        rom.gui.add_imgui(fallbackUi.renderWindow)
        rom.gui.add_to_menu_bar(fallbackUi.addMenuBar)
    end)

    logic.attach(module)
    module.activate()
end
"""


CURRENT_DATA_LUA = """
local data = {}

function data.buildStorage()
    return {}
end

return data
"""


CURRENT_LOGIC_LUA = """
local logic = {}

function logic.bind(data)
    return logic
end

function logic.buildActions()
    return {}
end

function logic.buildPatchPlan(host, runtime, plan)
    if runtime.data.read("FeatureEnabled") then
        host.logIf("Enabled")
    end
end

function logic.registerHooks(moduleRef)
    -- moduleRef.hooks.wrap("FunctionName", function(host, runtime, baseFunc, ...)
end

function logic.attach(moduleRef)
    moduleRef.actions.define(logic.buildActions())
    moduleRef.mutation.patch(logic.buildPatchPlan)
    logic.registerHooks(moduleRef)
end

return logic
"""


def write_template(root: Path, *, main: str = CURRENT_MAIN_LUA, logic: str = CURRENT_LOGIC_LUA) -> None:
    (root / "src" / "mods").mkdir(parents=True)
    (root / "src" / "main.lua").write_text(main, encoding="utf-8")
    (root / "src" / "mods" / "data.lua").write_text(CURRENT_DATA_LUA, encoding="utf-8")
    (root / "src" / "mods" / "logic.lua").write_text(logic, encoding="utf-8")


def write_coordinator(root: Path, display_name_marker: str) -> None:
    coordinator = root / "adamantRunDirector-RunDirector_Modpack"
    (coordinator / "src").mkdir(parents=True)
    (coordinator / "thunderstore.toml").write_text(
        """
[package]
namespace = "adamantRunDirector"
name = "RunDirector_Modpack"
versionNumber = "1.0.0"
""",
        encoding="utf-8",
    )
    (coordinator / "src" / "main.lua").write_text(
        f"""
local PACK_ID = "run-director"
local {display_name_marker} = "Run Director"
""",
        encoding="utf-8",
    )


def discover_coordinator_in(root: Path):
    old_root = create_module.ROOT_DIR
    create_module.ROOT_DIR = str(root)
    try:
        return create_module.discover_coordinator()
    finally:
        create_module.ROOT_DIR = old_root


def test_create_validator_accepts_current_contract() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_template(root)
        validate_current_lib_contract(str(root))


def test_create_validator_rejects_stale_contract() -> None:
    stale_main = CURRENT_MAIN_LUA + "\nlocal standaloneUi = lib.standaloneUiBridge(PLUGIN_GUID)\n"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_template(root, main=stale_main)
        try:
            validate_current_lib_contract(str(root))
        except RuntimeError as exc:
            assert "standaloneUiBridge" in str(exc)
        else:
            raise AssertionError("stale module template marker was accepted")


def test_create_writes_standalone_module_test_contract() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_template(root)
        write_module_test_contract(
            str(root),
            "adamantRunDirector-GodPool",
            "run-director",
            "GodPool",
        )
        validate_module_test_contract(str(root))

        workflow = (root / ".github" / "workflows" / "luacheck.yaml").read_text(encoding="utf-8")
        all_lua = (root / "tests" / "all.lua").read_text(encoding="utf-8")
        entrypoint_lua = (root / "tests" / "TestEntrypoint.lua").read_text(encoding="utf-8")

        assert "path: Submodules/${{ github.event.repository.name }}" in workflow
        assert "repository: h2-modpack/ModpackTools" in workflow
        assert "repository: h2-modpack/adamant-ModpackLib" in workflow
        assert "working-directory: Submodules/${{ github.event.repository.name }}" in workflow
        assert "find tests -type f -name '*.lua' -print0" in workflow
        assert "lua tests/all.lua" in workflow
        assert 'require("tests/TestEntrypoint")' in all_lua
        assert 'dofile("../../ModpackTools/tests/module_entrypoint_harness.lua")' in entrypoint_lua
        assert 'pluginGuid = "adamantRunDirector-GodPool"' in entrypoint_lua
        assert 'lu.assertEquals(boot.liveModule.getModuleId(), "GodPool")' in entrypoint_lua
        assert 'lu.assertEquals(boot.liveModule.getPackId(), "run-director")' in entrypoint_lua


def test_discover_coordinator_reads_pack_display_name() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_coordinator(root, "PACK_DISPLAY_NAME")

        coordinator = discover_coordinator_in(root)

        assert coordinator["pack_id"] == "run-director"
        assert coordinator["pack_name"] == "Run Director"
        assert coordinator["team"] == "adamantRunDirector"
        assert coordinator["coordinator_package"] == "RunDirector_Modpack"


def test_discover_coordinator_accepts_legacy_window_title() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_coordinator(root, "WINDOW_TITLE")

        coordinator = discover_coordinator_in(root)

        assert coordinator["pack_name"] == "Run Director"


def test_create_package_id_validation_matches_lib_identifier_shape() -> None:
    validate_package_id("Gameplay_QoL")
    validate_package_id("Balance_Changes")
    validate_package_id("LiveSplit")
    validate_package_id("QoL")
    validate_package_id("Select_First_Hammer")

    for value in ("Gameplay QoL", "Gameplay-QoL", "_Gameplay_QoL", "Gameplay_QoL_", "Gameplay__QoL", "1Gameplay"):
        try:
            validate_package_id(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid package id accepted: {value}")


def test_create_repo_name_uses_pack_namespace_without_pack_prefix() -> None:
    assert module_repo_name("adamantSpeedrun", "LiveSplit") == "adamantSpeedrun-LiveSplit"
    assert module_repo_name("adamantRunDirector", "Gameplay_QoL") == "adamantRunDirector-Gameplay_QoL"


def test_create_title_is_explicit_display_identity() -> None:
    assert validate_module_single_line(" Gameplay QoL ", "--title") == "Gameplay QoL"

    for value in ("", "   ", "Two\nLines"):
        try:
            validate_module_single_line(value, "--title")
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid title accepted: {value!r}")


def test_create_remote_parser_reads_github_org_and_repo() -> None:
    assert parse_github_remote("https://github.com/h2pack-speedrun/speedrun-modpack.git") == (
        "h2pack-speedrun",
        "speedrun-modpack",
    )
    assert parse_github_remote("git@github.com:h2pack-rundirector/run-director-modpack.git") == (
        "h2pack-rundirector",
        "run-director-modpack",
    )
    assert parse_github_remote("https://example.com/not-github/repo.git") == (None, None)


def main() -> int:
    tests = [
        test_create_validator_accepts_current_contract,
        test_create_validator_rejects_stale_contract,
        test_create_writes_standalone_module_test_contract,
        test_discover_coordinator_reads_pack_display_name,
        test_discover_coordinator_accepts_legacy_window_title,
        test_create_package_id_validation_matches_lib_identifier_shape,
        test_create_repo_name_uses_pack_namespace_without_pack_prefix,
        test_create_title_is_explicit_display_identity,
        test_create_remote_parser_reads_github_org_and_repo,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} new_module contract tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
