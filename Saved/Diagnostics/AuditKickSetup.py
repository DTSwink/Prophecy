import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
p=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/SwordThigh/BlueprintGraph.txt')
s=p.read_text(encoding='utf-8-sig')
for block in s.split('\n\n'):
    title=block.split('\n')[0]
    if any(k in title for k in ['Self Collision','Self-Collision','SelfCollision','Set Attack To Locomotion','Tempering']):
        print(block)
