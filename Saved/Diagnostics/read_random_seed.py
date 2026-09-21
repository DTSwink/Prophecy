import unreal,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent');cdo=unreal.get_default_object(bp.generated_class())
for w in [ed.get_editor_world(),ed.get_game_world()]:
 if not w:continue
 for a in [cdo]+list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)):
  try: print('SEED',a.get_path_name(),str(a.get_editor_property('Random Stream debug')))
  except Exception as e:print(str(e))
