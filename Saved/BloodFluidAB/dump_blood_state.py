import unreal
rows=[]
for comp in unreal.get_objects_of_class(unreal.NiagaraComponent):
    asset=None
    try: asset=comp.get_asset()
    except Exception: pass
    if not asset or asset.get_name()!='NS_bloodsplat':
        continue
    owner=comp.get_owner()
    world=comp.get_world()
    rows.append({
        'path': comp.get_path_name(),
        'world': world.get_name() if world else None,
        'owner': owner.get_name() if owner else None,
        'active': comp.is_active(),
        'visible': comp.is_visible(),
        'hidden_game': comp.get_editor_property('hidden_in_game'),
        'custom_depth': comp.get_editor_property('render_custom_depth'),
        'stencil': comp.get_editor_property('custom_depth_stencil_value'),
    })
print('PROPHECY_NS_BLOOD_STATE='+repr(rows))
