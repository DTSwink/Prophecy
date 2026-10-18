import unreal,pathlib,json
root=pathlib.Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy')
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
meshes=unreal.get_default_object(unreal.ProphecyBombLibrary).call_method('PrepareBombMeshes',(str(root/'Tools/BombFuse/Geometry.json'),))
assert len(meshes)==21,len(meshes)
for mesh in meshes:assert unreal.EditorAssetLibrary.save_loaded_asset(mesh,only_if_is_dirty=False),mesh
master=unreal.load_asset('/Game/_mygame/BombGenerated/M_BombBurn')
print('MASTER ATTRIBUTES',master.get_editor_property('use_material_attributes'))
print('PREPARED BOMB MESHES',len(meshes))
print(unreal.ProphecyBombLibrary.light_bomb_fuse.__doc__)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.Bomb.FuseAndDetonation')
