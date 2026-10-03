import unreal,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Set test mode before owned Play'
v=int(sys.argv[1]);assert v in (0,1)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.AttackWarmup '+str(v))
print('ATTACK_WARMUP',v)
