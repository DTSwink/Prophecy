import bpy
from pathlib import Path
src=Path(r'C:\Users\singerie\Documents\SmartsuitStudioProjects\kjb\MotionLibrary\SuperAlloy_Interactive-Right_hook_Fighter-a8f0f1b4.fbx')
out=Path(r'C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\DebugRootedManualConnectedTest.fbx')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(src), automatic_bone_orientation=False)
arm=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'][0]
action=bpy.data.actions[0]; arm.animation_data_create(); arm.animation_data.action=action
height=0-arm.data.bones['RightToeBase'].head_local.y
# fcurves
fcurves=[]
for layer in action.layers:
 for strip in layer.strips:
  for cb in strip.channelbags: fcurves.extend(cb.fcurves)
for fc in fcurves:
 if fc.data_path == 'pose.bones["Hips"].location' and fc.array_index == 1:
  for key in fc.keyframe_points:
   key.co.y -= height; key.handle_left.y -= height; key.handle_right.y -= height
  fc.update()
bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='EDIT')
for bone in arm.data.edit_bones:
    if not (bone.parent and bone.use_connect):
        bone.head.y += height
    bone.tail.y += height
hips=arm.data.edit_bones['Hips']
root=arm.data.edit_bones.new('Root')
root.head=(0,0,0); root.tail=(0,height,0)
hips.parent=root; hips.use_connect=False
bpy.ops.object.mode_set(mode='OBJECT')
# carrier
mesh=bpy.data.meshes.new('CarrierData'); obj=bpy.data.objects.new('RokokoCarrierMesh', mesh); bpy.context.collection.objects.link(obj)
verts=[]; faces=[]; weights=[]; size=.75; offs=[(size,0,0),(-size,0,0),(0,size,0),(0,0,size)]
for b in arm.data.bones:
 if b.name=='Root': continue
 c=b.head_local.copy(); start=len(verts)
 for o in offs: verts.append((c.x+o[0],c.y+o[1],c.z+o[2])); weights.append(b.name)
 faces += [(start,start+2,start+3),(start+2,start+1,start+3),(start+1,start,start+3),(start,start+1,start+2)]
mesh.from_pydata(verts, [], faces); mesh.update()
groups={b.name: obj.vertex_groups.new(name=b.name) for b in arm.data.bones}
for i,bn in enumerate(weights): groups[bn].add([i],1,'REPLACE')
obj.parent=arm; mod=obj.modifiers.new('Armature','ARMATURE'); mod.object=arm
bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); obj.select_set(True); bpy.context.view_layer.objects.active=arm
bpy.ops.export_scene.fbx(filepath=str(out), use_selection=True, object_types={'ARMATURE','MESH'}, add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X', use_armature_deform_only=False, armature_nodetype='ROOT', bake_anim=True, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False, bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True, bake_anim_step=1.0, bake_anim_simplify_factor=0.0, axis_forward='-Z', axis_up='Y')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(out), automatic_bone_orientation=False)
arm=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'][0]
for name in ['Root','Hips','Spine','Spine1','Spine2','Spine3','RightUpLeg','RightLeg','RightFoot','RightToeBase']:
 b=arm.data.bones[name]; print(name, tuple(round(x,3) for x in b.head_local), tuple(round(x,3) for x in b.tail_local), round(b.length,3), b.parent.name if b.parent else None, b.use_connect)
