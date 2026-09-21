import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent');c=unreal.get_default_object(bp.generated_class())
for a in [c]+list(unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(),bp.generated_class())):print(a.get_name(),a.get_editor_property('Random Stream debug').export_text())
