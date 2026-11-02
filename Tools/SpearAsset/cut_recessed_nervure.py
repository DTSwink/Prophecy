"""Cut an actual central channel, preserving the accepted blade silhouette."""
import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
BASE=ROOT/'Saved/Diagnostics/ImperialSpear/InitialDelivery/ImperialSpear_Source.blend'
scene=bpy.data.scenes['Scene']; bpy.context.window.scene=scene
art=bpy.data.collections['SPEAR • editable components']
blade=next(o for o in art.objects if o.name.startswith('06 •')); mat=blade.data.materials[0]
with bpy.data.libraries.load(str(BASE),link=False) as (src,dst):
    dst.objects=[name for name in src.objects if name.startswith('06 •')][:1]
baseline=dst.objects[0]; old=baseline.data
assert len(old.vertices)==584,'Expected the accepted original blade'
# Remove all earlier raised centre-strip constructions.
for ob in list(art.objects):
    if ob.name.startswith(('Blade • continuous straight steel nervure','Blade • uninterrupted inset gold hairline','Blade • continuous straight gold inlay','Blade • inlaid gold spine')):
        bpy.data.objects.remove(ob,do_unlink=True)
regions={'steel':(0,.25,.5,1),'edge':(.25,.375,.5,1),'ridge':(.375,.4375,.5,1),'steel_shadow':(.4375,.5,.5,1),'gold':(.5,.75,.5,1)}
def uv_for(kind,u,v):
    a,b,c,d=regions[kind]; pad=.003
    return (a+pad+u*(b-a-2*pad),c+pad+v*(d-c-2*pad))
vs=[]; fs=[]; kinds=[]; rows=[]; recess=[]
for k in range(len(old.vertices)//8):
    p=[old.vertices[k*8+j].co.copy() for j in range(8)]
    z=p[0].z; t=abs(p[2].y); wl=-p[0].x; wr=p[4].x
    taper=max(.003,(2.2-z)/.445)**.38
    half=min(.0017*taper,wl*.30,wr*.30)
    left_surface=t-(t-abs(p[1].y))*half/abs(p[1].x)
    right_surface=t-(t-abs(p[3].y))*half/abs(p[3].x)
    cut=min(.00060*taper,t*.30)
    floor=min(left_surface,right_surface)-cut
    # Points on the original faces form the lips. New walls slope INTO the blade.
    row=[tuple(p[0]),tuple(p[1]),(-half,-left_surface,z),(-.65*half,-floor,z),(-.22*half,-floor,z),(.22*half,-floor,z),(.65*half,-floor,z),(half,-right_surface,z),tuple(p[3]),tuple(p[4]),tuple(p[5]),(half,right_surface,z),(.65*half,floor,z),(.22*half,floor,z),(-.22*half,floor,z),(-.65*half,floor,z),(-half,left_surface,z),tuple(p[7])]
    vs.extend(row); rows.append(row)
    recess.append({'z_m':z,'channel_width_mm':half*2000,'depth_below_lip_mm':cut*1000,'gold_depth_below_original_crown_mm':(t-floor)*1000})
bands=['edge','steel','ridge','steel_shadow','gold','steel_shadow','ridge','steel','edge','edge','steel','ridge','steel_shadow','gold','steel_shadow','ridge','steel','edge']
for k in range(len(rows)-1):
    for j in range(18):
        fs.append((k*18+j,k*18+(j+1)%18,(k+1)*18+(j+1)%18,(k+1)*18+j)); kinds.append(bands[j])
fs.extend([tuple(reversed(range(18))),tuple((len(rows)-1)*18+j for j in range(18))]); kinds+=['steel','steel']
data=bpy.data.meshes.new('Original blade • true recessed nervure')
data.from_pydata(vs,[],fs); data.materials.append(mat); data.update()
bm=bmesh.new(); bm.from_mesh(data); bmesh.ops.recalc_face_normals(bm,faces=bm.faces); bm.to_mesh(data); bm.free()
uv=data.uv_layers.new(name='UV0_SurfaceAtlas')
for poly in data.polygons:
    poly.use_smooth=poly.index<(len(rows)-1)*18
    for li in poly.loop_indices:
        co=data.vertices[data.loops[li].vertex_index].co
        u=min(.99,max(.01,(co.x+.065)/.13)); v=min(.99,max(.01,(co.z-1.74)/.465))
        uv.data[li].uv=uv_for(kinds[poly.index],u,v)
# Keep hard cross-sectional lips, with smooth longitudinal shading.
custom=[]
for poly in data.polygons:
    if poly.index>=(len(rows)-1)*18: custom.extend([poly.normal[:]]*len(poly.loop_indices)); continue
    k,j=divmod(poly.index,18)
    for li in poly.loop_indices:
        ring=data.loops[li].vertex_index//18
        ns=[data.polygons[s*18+j].normal for s in [ring-1,ring] if 0<=s<len(rows)-1]
        custom.append(sum(ns,Vector()).normalized()[:])
data.normals_split_custom_set(custom)
blade.data=data
# All outer contour and original cutting-bevel points are copied verbatim.
mapping={0:0,1:1,3:8,4:9,5:10,7:17}
max_unchanged=0
for k in range(len(rows)):
    for old_j,new_j in mapping.items():
        max_unchanged=max(max_unchanged,(old.vertices[k*8+old_j].co-data.vertices[k*18+new_j].co).length)
assert max_unchanged==0
assert all(r['depth_below_lip_mm']>0 and r['gold_depth_below_original_crown_mm']>0 for r in recess)
bm=bmesh.new(); bm.from_mesh(data)
nonmanifold=sum(not e.is_manifold for e in bm.edges); bm.free()
assert nonmanifold==0
report={'baseline':str(BASE),'original_blade_vertex_count':len(old.vertices),'preserved_outer_contour_and_bevel_vertices':len(rows)*6,'max_preserved_vertex_movement_m':max_unchanged,
        'topology_changed_only_for_central_channel':True,'blade_closed_manifold':True,'channel':'Actual inset lips, sloped walls and a recessed floor on both faces; gold is a floor material, not a protruding strip.',
        'maximum_channel_width_mm':max(r['channel_width_mm'] for r in recess),'maximum_depth_below_lip_mm':max(r['depth_below_lip_mm'] for r in recess),
        'minimum_gold_depth_below_original_crown_mm':min(r['gold_depth_below_original_crown_mm'] for r in recess),
        'preserved':['original blade silhouette and cutting bevels','collar outline','shaft and moved grip','blunt gold pommel','tassel placement'],
        'stations':recess}
(OUT/'Shape_Preservation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.data.objects.remove(baseline,do_unlink=True)
scene['Spear_revision']='03: original blade silhouette; true recessed central channel with inset gold floor; smooth lacquer beads.'
scene['Preserve_original_blade_shape']=True
print(json.dumps({k:v for k,v in report.items() if k!='stations'}))
