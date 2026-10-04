import unreal,pathlib,json
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/FKPerAttackTiming20261004'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);assert ed.get_game_world() is None
assert ed.get_editor_world().get_path_name()=='/Game/testNN.testNN'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.UpgradeFKPerAttackTiming')
r=(p/'upgrade.txt').read_text(encoding='utf-8-sig');assert 'refreshed=2' in r and 'status=3' in r,r
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
r=(p.parent/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig');assert 'status=3' in r and 'native_properties=0 pin_types=0' in r,r
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(p/'after-graph.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
doc=unreal.ProphecyFKReturnLibrary.set_attack_fk_return.__doc__
for name in ['headbutt','hook_l','hook_r','jab_l','jab_r','kick_l','kick_r','over_l','over_r','pike','slash_l','slash_ld','slash_lu','slash_r','slash_rd','slash_ru']:assert name in doc,(name,doc)
(p/'reflection.json').write_text(json.dumps({'inspection':r,'signature':doc},indent=2))
print('UPGRADED_NODE_VERIFIED',r)