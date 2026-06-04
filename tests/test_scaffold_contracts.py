from __future__ import annotations

import sys
import tempfile
from pathlib import Path


SETUP_DIR = Path(__file__).resolve().parents[1]
SCAFFOLD_DIR = SETUP_DIR / "scaffold"
if str(SCAFFOLD_DIR) not in sys.path:
    sys.path.insert(0, str(SCAFFOLD_DIR))

from new_module import (  # noqa: E402
    module_repo_name,
    normalize_title,
    pascal_to_title,
    validate_current_lib_contract,
    validate_module_name,
    validate_package_name,
)
from new_pack import (  # noqa: E402
    coordinator_alias_prefix,
    coordinator_id,
    validate_coordinator_package,
    validate_org,
    validate_pack_id,
    validate_single_line,
    validate_team,
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


def test_new_module_validator_accepts_current_contract() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_template(root)
        validate_current_lib_contract(str(root))


def test_new_module_validator_rejects_stale_contract() -> None:
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


def test_new_module_title_fallback_preserves_known_acronyms() -> None:
    assert pascal_to_title("SelectFirstHammer") == "Select First Hammer"
    assert pascal_to_title("LiveSplit") == "Live Split"
    assert pascal_to_title("QoL") == "QoL"
    assert pascal_to_title("GameplayQoL") == "Gameplay QoL"
    assert pascal_to_title("TimerRTAIGT") == "Timer RTA IGT"
    assert pascal_to_title("LastRunLrT") == "Last Run LrT"


def test_new_module_name_validation_rejects_package_unsafe_names() -> None:
    validate_module_name("GameplayQoL")
    validate_module_name("QoL")

    for value in ("gameplayQoL", "Gameplay QoL", "Gameplay-QoL", "Gameplay_QoL", "1Gameplay"):
        try:
            validate_module_name(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid module name accepted: {value}")


def test_new_module_package_name_validation_allows_thunderstore_word_breaks() -> None:
    validate_package_name("Gameplay_QoL")
    validate_package_name("Balance_Changes")
    validate_package_name("Live_Split")
    validate_package_name("Select_First_Hammer")

    for value in ("Gameplay QoL", "Gameplay-QoL", "_Gameplay_QoL", "Gameplay_QoL_", "Gameplay__QoL"):
        try:
            validate_package_name(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid package name accepted: {value}")


def test_new_module_repo_name_uses_pack_namespace_without_pack_prefix() -> None:
    assert module_repo_name("adamantSpeedrun", "LiveSplit") == "adamantSpeedrun-LiveSplit"
    assert module_repo_name("adamantRunDirector", "Gameplay_QoL") == "adamantRunDirector-Gameplay_QoL"


def test_new_module_title_normalization_is_display_only() -> None:
    assert normalize_title(" Gameplay QoL ") == "Gameplay QoL"
    assert normalize_title(None) is None

    for value in ("", "   ", "Two\nLines"):
        try:
            normalize_title(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid title accepted: {value!r}")


def test_new_pack_uses_explicit_coordinator_package() -> None:
    assert coordinator_id("adamantSpeedrun", "Speedrun_Modpack") == "adamantSpeedrun-Speedrun_Modpack"
    assert coordinator_id("adamantRunDirector", "RunDirector_Modpack") == "adamantRunDirector-RunDirector_Modpack"
    assert coordinator_alias_prefix("Speedrun_Modpack") == "Speedrun"
    assert coordinator_alias_prefix("RunDirector_Modpack") == "RunDirector"
    assert coordinator_alias_prefix("CustomCoordinator") == "CustomCoordinator"


def test_new_pack_validation_rejects_ambiguous_names() -> None:
    validate_pack_id("speedrun")
    validate_pack_id("run-director")
    validate_single_line("Run Director", "--pack-name")
    validate_team("adamantRunDirector")
    validate_coordinator_package("RunDirector_Modpack")
    validate_org("h2pack-rundirector")

    invalid_cases = [
        (validate_pack_id, "RunDirector"),
        (validate_pack_id, "run_director"),
        (validate_pack_id, "run--director"),
        (lambda value: validate_single_line(value, "--pack-name"), ""),
        (lambda value: validate_single_line(value, "--pack-name"), "Two\nLines"),
        (validate_team, "_adamant"),
        (validate_team, "adamant-speedrun"),
        (validate_coordinator_package, "RunDirector-Modpack"),
        (validate_coordinator_package, "RunDirector__Modpack"),
        (validate_org, "-h2pack"),
        (validate_org, "h2pack_rundirector"),
    ]
    for validator, value in invalid_cases:
        try:
            validator(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid new_pack value accepted: {value!r}")


def test_coordinator_template_uses_current_framework_contract() -> None:
    main_lua = (SETUP_DIR / "templates" / "coordinator" / "src" / "main.lua").read_text(encoding="utf-8")
    contributing = (SETUP_DIR / "templates" / "coordinator" / "CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "Framework.createPack" in main_lua
    assert "Framework.createGuiCallbacks" in main_lua
    assert "rom.gui.add_imgui(callbacks.render)" in main_lua
    assert "rom.gui.add_always_draw_imgui(callbacks.alwaysDraw)" in main_lua
    assert "rom.gui.add_to_menu_bar(callbacks.menuBar)" in main_lua
    assert "Framework.tryInit" not in main_lua
    assert "definition.modpack" not in contributing
