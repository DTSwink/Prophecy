import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
cdo=unreal.get_default_object(bp.generated_class())
print('PIE',bool(ed.get_game_world()))
print('MEMBERS',[n for n in dir(cdo) if any(x in n.lower() for x in ['random','seed','stream'])])
try:print('VARIABLES',str(bp.get_editor_property('new_variables'))[:16000])
except Exception as e:print(e)
for w in [ed.get_editor_world(),ed.get_game_world()]:
 if not w:continue
 for a in [cdo]+list(unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)):
  props={}
  for n in ['random stream','random_stream','RandomStream','stream','seed']+[n for n in dir(cdo) if any(x in n.lower() for x in ['random','seed','stream'])]:
   try:
    v=a.get_editor_property(n)
    if isinstance(v,unreal.RandomStream):props[n]=str(v)
   except:pass
  print('STREAMS',a.get_path_name(),props)
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RandomStreamSeed';folder.mkdir(parents=True,exist_ok=True)
task=unreal.AssetExportTask();task.object=bp;task.filename=str(folder/'PoseAgent.copy');task.automated=True;task.prompt=False;task.replace_identical=True
try:print('EXPORT',unreal.Exporter.run_asset_export_task(task))
except Exception as e:print(e)
