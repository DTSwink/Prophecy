import unreal,json,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/HandEntryGate20261006'
dirty=list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
names=[x.get_name() for x in dirty]
print(json.dumps({'playing':bool(ed.get_game_world()),'dirty':names}))
allowed={'/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent','/Game/testNN','/Game/_mygame/SKM_UEFN_Mannequin',
 '/Game/_mygame/Materials/LimbColors/T_LimbPalette','/Game/_mygame/Materials/LimbColors/M_UEFN_LimbColors','/Game/_mygame/Materials/LimbColors/M_UEFN_Bicolor_LimbColors'}
packages=[x for x in dirty if x.get_name() in allowed]
if packages:assert unreal.EditorLoadingAndSavingUtils.save_packages(packages,True),'Save failed'
after=[x.get_name() for x in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]
assert not (set(after)&allowed),after
(p/'milestone-save.json').write_text(json.dumps({'saved':[x.get_name() for x in packages],'remaining_dirty':after,'playing':bool(ed.get_game_world())},indent=2))
print('MILESTONE_SAVE_OK')
