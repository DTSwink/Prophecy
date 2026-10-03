from pathlib import Path
p=Path('Saved/Diagnostics/CapturePin529Baseline.py');s=p.read_text().replace('Pin529Baseline','Pin529EveryTick').replace('pin529_baseline','pin529_everytick').replace('PIN529_BASELINE','PIN529_EVERYTICK')
s=s.replace("n=int(a.get_editor_property('tick debug'))", """n=int(a.get_editor_property('tick debug'))
   if n>=526 and not s.get('enabled'):
    lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyWalkPinningLibrary'))
    assert lib.call_method('SetWalkPinningEveryTick',args=(a,True))
    s['enabled']=True""")
s=s.replace("if n>=550:finish('Complete');return", """if n>=536 and not s.get('disabled'):
    lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyWalkPinningLibrary'))
    assert lib.call_method('SetWalkPinningEveryTick',args=(a,False))
    s['disabled']=True
   if n>=550:finish('Complete');return""")
Path('Saved/Diagnostics/CapturePin529EveryTick.py').write_text(s)
Path('Saved/Diagnostics/RunCapturePin529EveryTick.py').write_text("import pathlib,unreal\nsrc=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CapturePin529EveryTick.py'\nexec(compile(src.read_text(),str(src),'exec'),{'__name__':'pin529_everytick'})")
Path('Saved/Diagnostics/VerifyWalkTickPinning.py').write_text("""import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve Play'
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.WalkPinning+Prophecy.NN.Presentation')
print('TICK_PINNING_TESTS_QUEUED')
""")
