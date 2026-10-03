import unreal,pathlib
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
p=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/SwordThigh/BlueprintGraph.txt')
b=p.read_bytes();s=b.decode('utf-16' if b.startswith(b'\xff\xfe') else 'utf-8-sig')
for block in s.split('\n\n'):
    if ' | Set NN Wrist Freedom\n' in block: print(block)
