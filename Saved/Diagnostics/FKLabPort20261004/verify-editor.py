import unreal,pathlib,json
root=pathlib.Path(unreal.Paths.project_dir());p=root/'Saved/Diagnostics/FKLabPort20261004'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None
assert ed.get_editor_world().get_path_name()=='/Game/testNN.testNN'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.UseAcceptedFKLabProfiles')
r=(p/'profile-setup.txt').read_text(encoding='utf-8-sig');assert 'refreshed=2' in r and 'status=3' in r,r
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(p/'after-graph.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
doc=unreal.ProphecyFKReturnLibrary.set_attack_fk_return_profile.__doc__
for pin in ['inertia_hold','inertia_decay','world_inertia','spine_angle_time']:assert pin in doc,(pin,doc)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
r=(p.parent/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig');assert 'status=3' in r and 'native_properties=0 pin_types=0' in r,r
(p/'editor-verification.json').write_text(json.dumps({'status':r,'signature':doc,'map':ed.get_editor_world().get_name(),'saved':False},indent=2))
print('FK_LAB_PORT_EDITOR_OK',r)
