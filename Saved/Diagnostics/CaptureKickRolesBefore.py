import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
saved=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
raw=(saved/'SwordThigh/BlueprintGraph.txt').read_bytes()
(saved/'KickRolePinsBefore.txt').write_bytes(raw)
text=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
for block in text.split('\n\n'):
    if any(x in block.split('\n')[0] for x in ['Set Kick To Locomotion Blend','Set Kick Locomotion Lower Body Tempering']): print(block)
print('PLAY',bool(ed.get_game_world()))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'LiveCoding.Compile')
