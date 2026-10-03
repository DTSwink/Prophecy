import sys
import unreal


enabled = sys.argv[1].lower() == "true"
bp_class = unreal.EditorAssetLibrary.load_blueprint_class(
    "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent")
unreal.get_default_object(bp_class).set_editor_property(
    "show_kinematic_debug_mesh", enabled)
print("KINEMATIC_DEBUG_DEFAULT", enabled)
