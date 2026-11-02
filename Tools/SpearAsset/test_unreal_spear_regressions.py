"""Focused native regressions in the owned normally built diagnostic host."""
import os,pathlib,unreal
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/SpearPike20261030'
assert os.getpid()==int((out/'editor.pid').read_text().strip())
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),
    'Automation RunTests Prophecy.Spear+Prophecy.Jolt.HitEvents.CleanPike+Prophecy.Jolt.Constraints.PikeWoundCorrection')
print('Queued spear geometry/lifecycle, clean pike admission and wound correction regressions.')
