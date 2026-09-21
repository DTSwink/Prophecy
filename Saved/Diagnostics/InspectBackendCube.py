import unreal,json
rows=[]
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if not isinstance(a,unreal.ProphecyAgent):continue
    for c in a.get_components_by_class(unreal.StaticMeshComponent):
        if c.get_name()!='Cube':continue
        b=c.get_editor_property('body_instance')
        rows.append({'actor':a.get_actor_label(),'mobility':str(c.get_editor_property('mobility')),'simulate_physics':b.get_editor_property('simulate_physics'),'auto_weld':b.get_editor_property('auto_weld'),'parent':str(c.get_attach_parent()),'collision':str(c.get_collision_enabled())})
print('CUBE',json.dumps(rows))
