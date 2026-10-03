import json
from pathlib import Path
import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=ed.get_editor_world()
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackStartInertiaLibrary'))
assert lib.call_method('SetAttackStartFKCoreInertia',args=(None,False,.1,.3,.25,1.,1.)) is False
print('ATTACK_START_FK_CORE_REFLECTION_OK; user Play:',bool(ed.get_game_world()))
if not ed.get_game_world():
    unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.RepairLibraryDefaults')
    report=(Path(unreal.Paths.project_saved_dir())/'Diagnostics/LiveLibraryDefaults.txt').read_bytes()
    report=report.decode('utf-16' if report.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')
    assert 'status=3' in report,report
    assert 'other_values_and_wiring_preserved=1' in report,report
    print('ATTACK_START_FK_CORE_BLUEPRINT_OK '+report)
    unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.NN.AttackEntry.FKCore')
else:
    print('Blueprint compile and focused tests deferred to preserve user Play')
