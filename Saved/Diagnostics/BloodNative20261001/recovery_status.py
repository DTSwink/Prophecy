import unreal, json, pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert bp
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
assert bp.generated_class()
report=dict(world=ed.get_editor_world().get_path_name(),outside_pie=not bool(ed.get_game_world()),blueprint=bp.get_path_name(),generated_class=bp.generated_class().get_path_name(),saved=False)
pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/BloodNative20261001/recovery-status.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
