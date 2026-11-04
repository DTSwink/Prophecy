import bpy, numpy as np
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath='/mnt/user-data/uploads/Prophecy/Saved/BossUEFNCompatible/20260908_Stitched/SKM_Boss_UEFN_Fitted.fbx')
o=[o for o in bpy.data.objects if o.type=='MESH'][0]; me=o.data
n=len(me.vertices)
co=np.zeros(n*3); me.vertices.foreach_get('co',co); co=co.reshape(-1,3)
mw=np.array(o.matrix_world); cow=(np.c_[co,np.ones(n)]@mw.T)[:,:3]
nl=len(me.loops); lv=np.zeros(nl,np.int32); me.loops.foreach_get('vertex_index',lv)
uv=np.zeros(nl*2); me.uv_layers[0].data.foreach_get('uv',uv); uv=uv.reshape(-1,2)
pm=np.zeros(len(me.polygons),np.int32); me.polygons.foreach_get('material_index',pm)
ls=np.zeros(len(me.polygons),np.int32); me.polygons.foreach_get('loop_start',ls)
lt=np.zeros(len(me.polygons),np.int32); me.polygons.foreach_get('loop_total',lt)
loopmat=np.repeat(pm,lt)
np.savez('boss_dump.npz',co=co,cow=cow,lv=lv,uv=uv,loopmat=loopmat,mats=np.array([m.name for m in me.materials]),mw=mw)
print('ok',n)
