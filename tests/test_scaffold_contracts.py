from __future__ import annotations

import sys
import tempfile
from pathlib import Path


SETUP_DIR = Path(__file__).resolve().parents[1]
SCAFFOLD_DIR = SETUP_DIR / "scaffold"
if str(SCAFFOLD_DIR) not in sys.path:
    sys.path.insert(0, str(SCAFFOLD_DIR))

from new_module import validate_current_lib_contract  # noqa: E402


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
