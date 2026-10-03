import unreal


CHARACTER_PATH = "/Game/_mygame/MetaHumans/test"

character = unreal.load_asset(CHARACTER_PATH)
if character is None:
    raise RuntimeError("Missing MetaHuman Character: " + CHARACTER_PATH)

editor_subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
opened = editor_subsystem.open_editor_for_assets([character])
print("OPENED_ORIGINAL_METAHUMAN|{}|{}".format(
    character.get_path_name(), opened
))
