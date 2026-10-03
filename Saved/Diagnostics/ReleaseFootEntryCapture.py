import unreal,builtins,gc
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve Play'
state=getattr(builtins,'_foot_entry_probe',None)
if state is not None:
    state['actor']=None
    state['rows'].clear()
    del builtins._foot_entry_probe
del state
gc.collect()
unreal.SystemLibrary.collect_garbage()
print('FOOT_ENTRY_CAPTURE_RELEASED')
