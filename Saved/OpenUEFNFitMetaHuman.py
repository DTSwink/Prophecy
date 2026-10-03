import unreal


CHARACTER_PATH = "/Game/_mygame/MetaHumans/test_UEFNFit"

character = unreal.load_asset(CHARACTER_PATH)
if character is None:
    raise RuntimeError("Missing MetaHuman Character: " + CHARACTER_PATH)

editor_subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
opened = editor_subsystem.open_editor_for_assets([character])

try:
    content_browser = unreal.get_editor_subsystem(unreal.ContentBrowserSubsystem)
    content_browser.sync_browser_to_assets([character.get_path_name()])
except Exception as exc:
    unreal.log_warning("Could not sync Content Browser: {}".format(exc))

print("OPENED_METAHUMAN|{}|editor={}".format(
    character.get_path_name(), opened
))
