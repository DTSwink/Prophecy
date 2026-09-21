import builtins,unreal
print('PIE',unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor())
for key in ('_blood_visual','_blood_capture'):
 s=getattr(builtins,key,None)
 print(key,list(s) if s and key=='_blood_visual' else str(s))
print('DIRTY',[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()])
