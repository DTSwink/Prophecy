import pathlib
import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('USER_PLAY_ACTIVE', bool(ed.get_game_world()))
p = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/SwordThigh/BlueprintGraph.txt'
if p.exists():
    backup = p.with_name('BlueprintGraph-before-core-arms-audit.txt')
    if not backup.exists():
        backup.write_bytes(p.read_bytes())
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Prophecy.Sword.AuditCollisionGraph')
for name in ['Prophecy.UpperInertia.DebugDisable','Prophecy.UpperInertia.DebugResponse','Prophecy.UpperInertia.DebugNoTwist']:
    print(name, unreal.SystemLibrary.get_console_variable_float_value(name))
