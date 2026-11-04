import bpy, numpy as np, json
def load(p):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=p)
    o=[x for x in bpy.data.objects if x.type=='MESH'][0]; a=[x for x in bpy.data.objects if x.type=='ARMATURE'][0]; me=o.data
    n=len(me.vertices); co=np.zeros(n*3); me.vertices.foreach_get('co',co); co=co.reshape(-1,3)
    W=np.array(o.matrix_world); cow=(np.c_[co,np.ones(n)]@W.T)[:,:3]
    bones={b.name:(np.array(a.matrix_world)@np.array(b.matrix_local)) for b in a.data.bones}
    par={b.name:b.parent.name if b.parent else None for b in a.data.bones}
    nl=len(me.loops); uv=np.zeros(nl*2); me.uv_layers[0].data.foreach_get('uv',uv)
    nor=np.array([l.normal[:] for l in me.loops]) if hasattr(me,'corner_normals')==False else np.array([c.vector[:] for c in me.corner_normals])
    lv=np.zeros(nl,np.int32); me.loops.foreach_get('vertex_index',lv)
    wts={}
    for v in me.vertices:
        for g in v.groups:
            if g.weight>0: wts[(v.index,o.vertex_groups[g.group].name)]=g.weight
    sk=[k.name for k in me.shape_keys.key_blocks] if me.shape_keys else []
    skd={}
    if me.shape_keys:
        for k in me.shape_keys.key_blocks[1:]:
            c=np.zeros(n*3); k.data.foreach_get('co',c); skd[k.name]=c.reshape(-1,3)-co
    mats=[m.name for m in me.materials]
    return dict(cow=cow,bones=bones,par=par,uv=uv,nor=nor,lv=lv,wts=wts,sk=sk,skd=skd,mats=mats,W=W,arm=(a.name,tuple(a.scale)),obj=o.name)
A=load('/mnt/user-data/uploads/Prophecy/Saved/BossUEFNCompatible/20260908_Stitched/SKM_Boss_UEFN_Fitted.fbx')
B=load('/home/claude/face/out/SKM_Boss_UEFN_Fitted_Expressions.fbx')
r={}
r['names']=(A['arm'],A['obj'],B['arm'],B['obj'])
r['vertex_max_m']=float(np.abs(A['cow']-B['cow']).max())
r['bone_set_equal']=set(A['bones'])==set(B['bones']); r['hierarchy_equal']=A['par']==B['par']
r['bone_matrix_max']=float(max(np.abs(A['bones'][k]-B['bones'][k]).max() for k in A['bones']))
r['loop_order_equal']=bool((A['lv']==B['lv']).all()); r['uv_max']=float(np.abs(A['uv']-B['uv']).max())
r['normal_max']=float(np.abs(A['nor']-B['nor']).max())
r['weights_keys_equal']=set(A['wts'])==set(B['wts']); r['weight_max']=float(max(abs(A['wts'][k]-B['wts'][k]) for k in A['wts']))
r['materials_equal']=A['mats']==B['mats']; r['shape_keys']=B['sk']
D=np.load('/home/claude/face/boss_deltas.npz'); errs=[]
for nm in D['names']:
    exp=np.zeros_like(B['cow']); exp[D[nm+'_idx']]=D[nm+'_d']
    got=(B['skd'][nm]@B['W'][:3,:3].T)
    errs.append(float(np.abs(got-exp).max()))
r['shape_delta_max_err_m']=max(errs)
print(json.dumps(r,indent=1,default=str)); json.dump(r,open('/home/claude/face/out/roundtrip_verification.json','w'),indent=1,default=str)
