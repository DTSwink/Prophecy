import sys
import unreal

path = sys.argv[1] if len(sys.argv) > 1 else "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent"
asset = unreal.EditorAssetLibrary.load_asset(path)
if not asset:
    raise RuntimeError("Missing asset " + path)
unreal.get_editor_subsystem(unreal.AssetEditorSubsystem).open_editor_for_assets([asset])
print("OPENED " + path)
