"""Remove only unused task-created candidate shader data, after shared-gold switch."""
import bpy,json
prefixes=('02 • carved lotus pommel body','Pommel • rolled socket and straight barrel','Pommel • stepped lotus seat','Pommel • six carved lotus petals')
removed_meshes=[]
for m in list(bpy.data.meshes):
    if m.users==0 and m.name.startswith(prefixes):removed_meshes.append(m.name);bpy.data.meshes.remove(m)
removed_materials=[]
for m in list(bpy.data.materials):
    if m.name in ('M_ImperialSpear_PommelGold','TEMP_Lotus_Clay'):
        assert m.users==0,(m.name,m.users)
        removed_materials.append(m.name);bpy.data.materials.remove(m)
removed_images=[]
for im in list(bpy.data.images):
    if im.name.startswith('T_ImperialSpear_LotusGold_'):
        assert im.users==0,(im.name,im.users)
        removed_images.append(im.name);bpy.data.images.remove(im)
assert all(o.data.materials[0].name=='M_ImperialSpear_PBR' for o in bpy.data.collections['SPEAR • editable components'].objects if o.type=='MESH')
print(json.dumps({'orphan_task_meshes_removed':len(removed_meshes),'unused_candidate_materials_removed':removed_materials,'unused_candidate_images_removed':removed_images}))
