import unreal,builtins,gc
s=getattr(builtins,'_attack_start_probe',None)
if s:s['rows']=[];s['actor']=None
if hasattr(builtins,'_attack_start_probe'):del builtins._attack_start_probe
gc.collect()
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('ATTACK_START_FINAL_PLAY_ACTIVE',bool(ed.get_game_world()))
print('KNEE_TRIAL_MODE',unreal.SystemLibrary.get_console_variable_int_value('Prophecy.Tempering.KneePlane'))
