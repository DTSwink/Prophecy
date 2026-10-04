import unreal,json,pathlib,shutil
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/FKPerAttackTiming20261004'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None
assert json.loads((p/'graph-verification.json').read_text())['verified']
r=json.loads((p/'tests-headless/index.json').read_text(encoding='utf-8-sig'));assert r['succeeded']==12 and r['failed']==0
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
r=(p.parent/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig');assert 'status=3' in r and 'native_properties=0 pin_types=0' in r,r
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
f=pathlib.Path(unreal.Paths.project_content_dir())/'_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset';shutil.copy2(f,p/'BP-upgraded-saved.uasset')
(p/'complete.json').write_text(json.dumps({'map':ed.get_editor_world().get_path_name(),'play':False,'tests_passed':12,'inspection':r,'saved':str(f),'default_hold':.1,'default_trim':.34},indent=2))
print('SAVED_PER_ATTACK_HOLD_TRIM',r)
