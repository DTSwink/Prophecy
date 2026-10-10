import unreal,json,pathlib
out=pathlib.Path(unreal.Paths.project_dir())/'Labs/SwordHolsterLab/data'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
actors=unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(),unreal.ProphecyAgent)
a=next(a for a in actors if any(c.get_name()=='holster' for c in a.get_components_by_class(unreal.SceneComponent)))
h=next(c for c in a.get_components_by_class(unreal.SceneComponent) if c.get_name()=='holster')
ref=next(c for c in a.get_components_by_class(unreal.ChildActorComponent) if c.get_name().startswith('SwordRef'))
sword=ref.get_editor_property('child_actor');blade=next(c for c in sword.get_components_by_class(unreal.StaticMeshComponent) if c.get_name()=='sword')
base=next(c for c in sword.get_components_by_class(unreal.SceneComponent) if c.get_name() in ['base blade','blade base'])
mesh=a.get_pose_reference_mesh();pelvis=mesh.get_socket_transform('pelvis')
def v(x):return [x.x,x.y,x.z]
def t(x):return {'p':v(x.translation),'q':[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w],'s':v(x.scale3d)}
def geometry(m):
 result={'asset':m.get_path_name(),'sections':[]}
 for i in range(m.get_num_sections(0)):
  vertices,triangles,normals,uvs,tangents=unreal.ProceduralMeshLibrary.get_section_from_static_mesh(m,0,i)
  result['sections'].append({'vertices':[v(x) for x in vertices],'triangles':list(triangles)})
 return result
result={'actor':a.get_path_name(),'coordinates':'Unreal XYZ cm, quaternion XYZW','pelvis':t(pelvis),
 'holster':t(unreal.MathLibrary.make_relative_transform(h.get_world_transform(),pelvis)),
 'seated':t(unreal.MathLibrary.make_relative_transform(blade.get_world_transform(),h.get_world_transform())),
 'grip':t(a.get_editor_property('sword_grip_transform')),
 'assetScale':v(blade.get_world_transform().scale3d),
 'baseBladeWorld':v(base.get_world_transform().translation),
 'baseBladeLocal':v(unreal.MathLibrary.inverse_transform_location(blade.get_world_transform(),base.get_world_transform().translation)),
 'swordMesh':geometry(unreal.load_asset('/Game/_mygame/sword/geometry/Sword_GL01_Training')),'holsterMesh':geometry(h.static_mesh)}
reference=geometry(blade.static_mesh)
result['bladeLength']=(max(v[2] for section in reference['sections'] for v in section['vertices'])-result['baseBladeLocal'][2])*result['assetScale'][2]
(out/'unreal-setup.json').write_text(json.dumps(result),encoding='utf-8')
print('DS_SETUP_EXPORTED',result['actor'],len(result['swordMesh']['sections']),len(result['holsterMesh']['sections']))

