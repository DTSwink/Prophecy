"""Disable inherited diagnostic-only nodes in the copied spear Blueprint."""
import os,pathlib,json,unreal
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/SpearPike20261030'
assert os.getpid()==int((out/'editor.pid').read_text().strip())
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
bp=unreal.load_asset('/Game/_mygame/spear/A_Spear')
targets=['K2Node_CallFunction_1','K2Node_CallFunction_18','K2Node_CallFunction_117']
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
paths={name:bp.get_path_name()+':EventGraph.'+name for name in targets}
# Kismet's reflected property setters support the node's enum/boolean fields.
# Use exact objects in the copy, then compile to regenerate its bytecode.
nodes={name:unreal.find_object(None,path) for name,path in paths.items()}
assert all(node and node.get_path_name()==paths[name] for name,node in nodes.items())
system=unreal.get_default_object(unreal.SystemLibrary.static_class())
bp.modify()
for name in targets:
    node=nodes[name];node.modify()
    system.call_method('SetBytePropertyByName',(node,unreal.Name('EnabledState'),1))
    system.call_method('SetBoolPropertyByName',(node,unreal.Name('bUserSetEnabledState'),True))
    unreal.SystemLibrary.execute_console_command(world,'GETALL K2Node_CallFunction EnabledState OUTER='+bp.get_path_name()+':EventGraph NAME='+name)
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Spear.Install')
assert 'status=3' in (out/'SpearSetup.txt').read_text(encoding='utf-8-sig')
# Flesh cleanup returns to the authored Sword channel; start on that channel
# too, so a fresh standalone spawn and a post-pike spear behave identically.
ss=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
for handle in ss.k2_gather_subobject_data_for_blueprint(bp):
    obj=unreal.SubobjectDataBlueprintFunctionLibrary.get_object(unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle))
    if obj.get_name()=='sword_GEN_VARIABLE':
        obj.modify();obj.set_collision_object_type(unreal.CollisionChannel.ECC_SWORD)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
(out/'disabled-test-node-commands.json').write_text(json.dumps({'paths':paths,'requested_state':'Disabled'},indent=2))
print('Saved copied spear with disabled diagnostic nodes; verify GETALL log and prelaunch velocity.')
