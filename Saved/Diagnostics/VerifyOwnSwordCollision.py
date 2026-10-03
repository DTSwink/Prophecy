import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('OWN_SWORD_USER_PLAY',bool(ed.get_game_world()))
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySwordPhysicsLibrary'))
lib.call_method('SetOwnSwordCollisionEnabled',(None,False))
print('OWN_SWORD_NODE_REFLECTED')
if not ed.get_game_world():
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RepairLibraryDefaults')
    data=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/LiveLibraryDefaults.txt').read_bytes()
    report=data.decode('utf-16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')
    assert ('status=3' in report or 'status=5' in report) and 'other_values_and_wiring_preserved=1' in report,report
    print('OWN_SWORD_BLUEPRINT',report)
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Jolt.Sword.AttackCollisionPhases')
else:
    print('OWN_SWORD_COMPILE_TESTS_DEFERRED_PRESERVE_USER_PLAY')
