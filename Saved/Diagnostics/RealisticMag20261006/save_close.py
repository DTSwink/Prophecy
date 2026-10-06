import unreal,json,pathlib,shutil
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RealisticMag20261006'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
content=unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages();maps=unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
for pkg in [*content,*maps]:
 name=pkg.get_name();assert name.startswith('/Game/'),name
 f=pathlib.Path(unreal.Paths.project_content_dir())/(name[6:]+('.umap' if pkg in maps else '.uasset'))
 if f.exists():shutil.copy2(f,p/(f.name+'.before-save'))
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent');unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
r=(p.parent/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in r and 'native_properties=0 pin_types=0' in r,r
assert unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True,True),'Save failed; editor preserved'
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
(p/'saved.json').write_text(json.dumps({'content':[x.get_name() for x in content],'maps':[x.get_name() for x in maps],'inspection':r},indent=2))
print('SAVED_CURRENT_BLUEPRINT_AND_MAP')
unreal.SystemLibrary.quit_editor()
