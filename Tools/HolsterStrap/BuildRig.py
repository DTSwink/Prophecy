"""Blender --background --factory-startup --python Tools/HolsterStrap/BuildRig.py.
Extract complementary rigid/weighted meshes without editing the source file.
"""
import bpy,json,pathlib
from mathutils import Vector, Matrix
root=pathlib.Path(__file__).resolve().parents[2]
out=root/'Saved/Diagnostics/HolsterStrap20261013';out.mkdir(parents=True,exist_ok=True)
exports=pathlib.Path(r'C:/Users/singerie/Downloads/HolsterStrap');exports.mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r'C:/Users/singerie/Downloads/sword_in_scabbard.FBX')
source=next(o for o in bpy.context.scene.objects if o.type=='MESH');m=source.data
parent=list(range(len(m.vertices)))
def find(x):
    while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
    return x
for edge in m.edges:a,b=map(find,edge.vertices);parent[a]=b
parts={}
for v in m.vertices:parts.setdefault(find(v.index),[]).append(v.index)
parts=sorted(parts.values(),key=lambda x:-len(x))
removed={0,16,17,18,19,40,43,44}
strap_parts={1,20,21} # Only the leather and its two loose-end rivets need skinning.
def subset(name,part_ids):
    ids=sorted(v for i in part_ids for v in parts[i]);lookup={v:i for i,v in enumerate(ids)}
    faces=[p for p in m.polygons if p.vertices[0] in lookup]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata([source.matrix_world@m.vertices[v].co for v in ids],[],[[lookup[v] for v in p.vertices] for p in faces]);mesh.update();mesh.materials.append(m.materials[0])
    uv=mesh.uv_layers.new(name=m.uv_layers[0].name)
    for p,src in zip(mesh.polygons,faces):
        p.use_smooth=src.use_smooth
        for a,b in zip(p.loop_indices,src.loop_indices):uv.data[a].uv=m.uv_layers[0].data[b].uv
    normals=[source.matrix_world.to_3x3().inverted().transposed()@m.corner_normals[li].vector for p in faces for li in p.loop_indices]
    mesh.normals_split_custom_set([v.normalized() for v in normals])
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    return obj,ids
rigid,rigid_ids=subset('HolsterRigid',set(range(len(parts)))-removed-strap_parts)
strap,strap_ids=subset('HolsterStrap',strap_parts)
assert set(rigid_ids).isdisjoint(strap_ids)
assert len(rigid_ids)+len(strap_ids)==6053
strap_coords={v:source.matrix_world@m.vertices[v].co for v in parts[1]}
def center(y):
    hits=[]
    for e in m.edges:
        if not all(v in strap_coords for v in e.vertices):continue
        a,b=[strap_coords[v] for v in e.vertices]
        if min(a.y,b.y)<=y<=max(a.y,b.y) and abs(a.y-b.y)>1e-9:hits.append(a.lerp(b,(y-a.y)/(b.y-a.y)))
    return Vector(((min(v.x for v in hits)+max(v.x for v in hits))*.5,y,(min(v.z for v in hits)+max(v.z for v in hits))*.5))
points=[center(y) for y in [.045,.076,.107,.138,.169,.201]]
bpy.ops.object.select_all(action='DESELECT');arm_data=bpy.data.armatures.new('HolsterStrapRig');arm=bpy.data.objects.new('HolsterStrapRig',arm_data);bpy.context.collection.objects.link(arm);arm.select_set(True);bpy.context.view_layer.objects.active=arm
bpy.ops.object.mode_set(mode='EDIT');root_bone=arm_data.edit_bones.new('strap_root');root_bone.head=(0,0,0);root_bone.tail=(0,.02,0)
last=root_bone
for i in range(5):
    b=arm_data.edit_bones.new(f'strap_{i+1:02d}');b.head=points[i];b.tail=points[i+1];b.parent=last;b.use_connect=i>0;last=b
tip=arm_data.edit_bones.new('strap_tip');tip.head=points[-1];tip.tail=points[-1]+(points[-1]-points[-2]).normalized()*.004;tip.parent=last;tip.use_connect=True
bpy.ops.object.mode_set(mode='OBJECT')
groups={n:strap.vertex_groups.new(name=n) for n in ['strap_root',*[f'strap_{i+1:02d}' for i in range(5)],'strap_tip']}
for v in strap.data.vertices:
    # Fixed wrapped leather/rivets below the buckle; smooth weights on the tail.
    y=v.co.y
    if y<=points[0].y:groups['strap_root'].add([v.index],1,'REPLACE');continue
    u=min(4.999999,(y-points[0].y)/(points[-1].y-points[0].y)*5)
    j=int(u);t=u-j
    a='strap_root' if j==0 else f'strap_{j:02d}';b=f'strap_{j+1:02d}'
    groups[a].add([v.index],1-t,'REPLACE');groups[b].add([v.index],t,'REPLACE')
mod=strap.modifiers.new('Strap skinning','ARMATURE');mod.object=arm;strap.parent=arm
bpy.data.objects.remove(source,do_unlink=True)
# Bake centimetres into mesh/armature data, not an inherited 100x root scale.
for obj in [rigid,strap,arm]:obj.data.transform(Matrix.Scale(100,4))
bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=.01
def export(name,objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:o.select_set(True)
    bpy.context.view_layer.objects.active=objs[0]
    bpy.ops.export_scene.fbx(filepath=str(exports/(name+'.fbx')),use_selection=True,object_types={'MESH','ARMATURE'},use_mesh_modifiers=False,add_leaf_bones=False,bake_anim=False,mesh_smooth_type='OFF',axis_forward='-Z',axis_up='Y',primary_bone_axis='Y',secondary_bone_axis='X',apply_unit_scale=True)
export('HolsterRigid',[rigid]);export('HolsterStrap',[strap,arm])
bpy.ops.object.select_all(action='SELECT');bpy.context.view_layer.objects.active=arm
bpy.ops.wm.save_as_mainfile(filepath=str(exports/'HolsterStrap.blend'))
report={'rigid_vertices':len(rigid.data.vertices),'strap_vertices':len(strap.data.vertices),'rigid_triangles':len(rigid.data.polygons),'strap_triangles':len(strap.data.polygons),'points_m':[list(v) for v in points],'bone_names':[b.name for b in arm_data.bones],'exports':str(exports),'combined_original_vertex_count':len(rigid_ids)+len(strap_ids)}
(out/'rig.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
