import unreal

path = "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent"
bp = unreal.load_asset(path)
name = "UseJuly5WalkFineTune"
try:
    pin = unreal.EdGraphPinType()
    pin.import_text('(PinCategory="bool")')
    if not unreal.BlueprintEditorLibrary.add_member_variable(bp, name, pin):
        raise RuntimeError("Could not add UseJuly5WalkFineTune")
except Exception as exc:
    if "already" not in str(exc).lower():
        raise
unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(bp, name, True)
unreal.KismetEditorUtilities.compile_blueprint(bp) if hasattr(unreal, "KismetEditorUtilities") else None
unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
print("JULY_WALK_CHECKBOX_READY", path, name)
