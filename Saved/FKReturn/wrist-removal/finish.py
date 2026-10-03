import unreal,shutil
from pathlib import Path
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play; defer migration and tests'
root=Path(unreal.Paths.project_dir()).resolve()
dest=root/'Saved/FKReturn/wrist-removal'
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
shutil.copy2(root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt',dest/'graph-before.txt')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RetireWristRecoil')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
shutil.copy2(root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt',dest/'graph-after.txt')
print((dest/'migration.txt').read_text(encoding='utf-8-sig'))
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.Physics.ArmCone.DisabledByDefault+Prophecy.Physics.ArmCone.RegionalLifecycle+Prophecy.Physics.ArmCone.FeedbackOnlyCorrectedArms')
