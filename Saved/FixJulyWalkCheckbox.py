import unreal

path = "/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent"
name = "UseJuly5WalkFineTune"
bp = unreal.load_asset(path)

try:
    variables = bp.get_editor_property("new_variables")
    names = {str(variable.get_editor_property("var_name")) for variable in variables}
except Exception:
    names = set()

if name not in names:
    pin = unreal.EdGraphPinType()
    pin.import_text('(PinCategory="bool")')
    if not unreal.BlueprintEditorLibrary.add_member_variable(bp, name, pin):
        raise RuntimeError("Failed to add checkbox to Blueprint")

unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(bp, name, True)
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)

subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
subsystem.close_all_editors_for_asset(bp)
subsystem.open_editor_for_assets([bp])
print("CHECKBOX_FIXED", path, name)
