import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LocoDragFreeze20261002'
d=dict(play_active=ed.get_game_world() is not None)
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
(p/'rename-before.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
if not d['play_active']:
 # Capture immediately before reconstruction, preserving any intervening user edits.
 unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RefreshFootLocomotionHandoff')
 d['refresh']=(p.parent/'FootLocomotionHandoffPins.txt').read_text(encoding='utf-8-sig')
 unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
 (p/'rename-after.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
data=(p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes()
graph=data.decode('utf16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')
d['renamed_node_visible']=' | Set Attack Loco Drag\n' in graph.replace('\r\n','\n')
(p/'rename.json').write_text(json.dumps(d,indent=2),encoding='utf8')
print('LOCO_DRAG_RENAME',d)
