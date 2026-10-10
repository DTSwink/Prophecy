import unreal,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
a=unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(),unreal.ProphecyAgent)[0]
c=next(c for c in a.get_components_by_class(unreal.ChildActorComponent) if c.get_name().startswith('SwordRef'))
s=c.get_editor_property('child_actor');m=s.get_component_by_class(unreal.StaticMeshComponent)
print('bounds',m.get_local_bounds(),'sockets',m.get_all_socket_names())
print('properties',[x for x in dir(s) if any(w in x.lower() for w in ['blade','length','tip','start','end','guard'])])
print('grip',a.get_editor_property('sword_grip_transform'))
print('mesh',a.get_editor_property('sword_training_mesh'))
