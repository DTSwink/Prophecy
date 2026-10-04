import unreal,json,pathlib,hashlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/FKLabPort20261004'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None
assert ed.get_editor_world().get_path_name()=='/Game/testNN.testNN'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(p/'after-graph.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
tests=json.loads((p/'tests-complete/index.json').read_text(encoding='utf-8-sig'));assert tests['succeeded']==10 and tests['failed']==0
content=[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
maps=[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
assert not content and not maps,(content,maps)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.FKReturn.Audit 0')
receipt={'normal_dll':True,'map':'/Game/testNN','play':False,'dirty_content':content,'dirty_maps':maps,'tests_passed':10,'scene':json.loads((p/'scene-verification.json').read_text())}
(p/'completion.json').write_text(json.dumps(receipt,indent=2))
print('FK_LAB_PORT_COMPLETE: normal DLL, TestNN, no Play or unsaved assets, 10 passing tests.')
