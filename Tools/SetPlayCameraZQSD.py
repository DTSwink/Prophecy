"""Apply project camera mappings live, without taking over Play."""
import sys,unreal
def key(name):
    value=unreal.Key()
    value.import_text(name)
    return value
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world() or ed.get_editor_world()
if '--build' in sys.argv:
    unreal.SystemLibrary.execute_console_command(w,'LiveCoding.Compile')
    print('Camera binding helper build dispatched')
else:
    settings=unreal.get_default_object(unreal.InputSettings)
    for axis,old,new,scale in [('FlyCam_MoveFB','W','Z',1.),('FlyCam_MoveLR','A','Q',-1.)]:
        settings.remove_axis_mapping(unreal.InputAxisKeyMapping(axis_name=axis,key=key(old),scale=scale),force_rebuild_keymaps=False)
        settings.add_axis_mapping(unreal.InputAxisKeyMapping(axis_name=axis,key=key(new),scale=scale),force_rebuild_keymaps=False)
        mappings=settings.get_axis_mapping_by_name(axis)
        print([(str(m.axis_name),m.key.export_text(),m.scale) for m in mappings])
        assert any(m.key.export_text()==key(new).export_text() and m.scale==scale for m in mappings)
        assert not any(m.key.export_text()==key(old).export_text() and m.scale==scale for m in mappings)
    settings.force_rebuild_keymaps()
    unreal.SystemLibrary.execute_console_command(w,'Prophecy.DebugCamera.InstallInput')
    print('ZQSD camera mappings applied; existing Play and scene untouched')
