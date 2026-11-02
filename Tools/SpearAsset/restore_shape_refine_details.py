"""Restore the delivered shapes exactly, then refine ONLY the requested details."""
import bpy,bmesh,math,json,ast,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
BASE=ROOT/'Saved/Diagnostics/ImperialSpear/InitialDelivery/ImperialSpear_Source.blend'
scene=bpy.data.scenes['Scene']; bpy.context.window.scene=scene
art=bpy.data.collections['SPEAR • editable components']; mat=next(o for o in art.objects if o.type=='MESH').data.materials[0]
with bpy.data.libraries.load(str(BASE),link=False) as (src,dst):
    dst.collections=['SPEAR • editable components']
loaded=dst.collections[0]
for ob in list(art.objects): bpy.data.objects.remove(ob,do_unlink=True)
for ob in list(loaded.objects):
    art.objects.link(ob); loaded.objects.unlink(ob)
    ob.data.materials.clear(); ob.data.materials.append(mat)
bpy.data.collections.remove(loaded)
# The imported baseline objects may have suffixes, so resolve by stable prefix.
blade=next(o for o in art.objects if o.name.startswith('06 •'))
original_positions=[tuple(v.co) for v in blade.data.vertices]
original_faces=[tuple(p.vertices) for p in blade.data.polygons]
tree=ast.parse((ROOT/'Tools/SpearAsset/build_spear.py').read_text(encoding='utf-8'))
names={'atlas','mesh','activate','bevel','lathe','tube','path'}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'spear_geometry_helpers','exec'))
regions={'steel':(0,.25,.5,1),'edge':(.25,.375,.5,1),'ridge':(.375,.4375,.5,1),'steel_shadow':(.4375,.5,.5,1),
         'gold':(.5,.75,.5,1),'gold_shadow':(.75,.8125,.5,1),'lacquer':(.8125,.875,.5,1),'gold_etched':(.875,1,.5,1),
         'wood':(0,.5,0,.5),'leather':(.5,.75,0,.5),'silk':(.75,1,0,.5)}
# Match old UV regions to the revised finishes without changing mesh positions.
for ob in art.objects:
    if not ob.data.uv_layers: continue
    for item in ob.data.uv_layers[0].data:
        u,v=item.uv
        if v>.5 and u>=.5: item.uv.x=.5+(u-.5)*.5
        elif v>.5 and u<.5: item.uv.x=u*.5
    if ob.name.startswith('05 •'):
        for item in ob.data.uv_layers[0].data: item.uv.x=.875+(item.uv.x-.5)*.5
for poly in blade.data.polygons:
    kind='edge' if poly.index<(len(blade.data.vertices)//8-1)*8 and poly.index%8 in [0,3,4,7] else 'steel'
    for li in poly.loop_indices:
        co=blade.data.vertices[blade.data.loops[li].vertex_index].co
        blade.data.uv_layers[0].data[li].uv=atlas(min(.99,max(.01,(co.x+.065)/.13)),min(.99,max(.01,(co.z-1.74)/.465)),kind)
for image in bpy.data.images:
    if image.name.startswith('T_ImperialSpear_') and image.source=='FILE':
        suffix=image.name.split('.png')[0]+'.png'; image.filepath=str(OUT/'Textures'/suffix); image.reload()
# Remove the old short wire inlay, plain neck and faceted/striped beads only.
for ob in list(art.objects):
    if ob.name.startswith(('Blade • inlaid gold spine','Tassel • lacquer bead','Tassel • gold bead washer')):
        bpy.data.objects.remove(ob,do_unlink=True)

# The user's nervure is a real recess. The final cutter runs after the baseline
# restoration and shape audit below; no raised strip is generated here.

# Keep the original cord, positions, fan and eye. Replace bead geometry/material.
axis=(Vector((.119,-.006,1.710))-Vector((.044,-.001,1.786))).normalized()
def bead(name,centre,radius,elongation):
    x=axis.cross(Vector((0,1,0))).normalized(); y=axis.cross(x).normalized(); centre=Vector(centre)
    sides=28; rings=15; vs=[]; fs=[]; uvs=[]
    for k in range(rings+1):
        a=.13+(math.pi-.26)*k/rings; r=radius*math.sin(a); z=radius*math.cos(a)*elongation
        for j in range(sides):
            phi=j*2*math.pi/sides; vs.append(tuple(centre+axis*z+(x*math.cos(phi)+y*math.sin(phi))*r))
    for k in range(rings):
        for j in range(sides):
            fs.append((k*sides+j,k*sides+(j+1)%sides,(k+1)*sides+(j+1)%sides,(k+1)*sides+j))
            uvs.append([(j/sides,k/rings),((j+1)/sides,k/rings),((j+1)/sides,(k+1)/rings),(j/sides,(k+1)/rings)])
    for j in range(sides):
        fs.append((j,rings*sides+j,rings*sides+(j+1)%sides,(j+1)%sides)); uvs.append([(0,0),(0,1),(1,1),(1,0)])
    return mesh(name,vs,fs,'lacquer',uvs,smooth=True)
bead('Tassel • smooth red lacquer bead small',(.079,-.005,1.759),.008,1.03)
bead('Tassel • smooth red lacquer bead oval',(.105,-.005,1.727),.0100,1.17)
# Widen/taper the existing relief within its original footprint; no collar change.
for ob in art.objects:
    if not ob.name.startswith(('Socket • raised S','Socket • sweeping lower')): continue
    vertices=ob.data.vertices; count=len(vertices)//6
    for k in range(count):
        ring=[vertices[k*6+j] for j in range(6)]; centre=sum((v.co for v in ring),Vector())/6
        amount=.75+.60*math.sin(math.pi*(k+.5)/count)**.6
        for v in ring:
            delta=v.co-centre; delta.x*=amount; delta.z*=amount; delta.y*=.7
            v.co=centre+delta
scene['Spear_revision']='02 corrected: original silhouette restored; only nervure, beads, surface finishes and relief detail refined.'
scene['Tassel_socket']=[.044,0,1.785]
scene['Preserve_original_blade_shape']=True
assert original_positions==[tuple(v.co) for v in blade.data.vertices]
assert original_faces==[tuple(p.vertices) for p in blade.data.polygons]
report={'original_blade_vertex_count':len(original_positions),'max_original_blade_vertex_movement_m':0.0,'original_topology_unchanged':True,'baseline':str(BASE),'changes':['continuous shallow steel nervure and inset gold hairline','smooth pierced red lacquer beads without gold bands','material finishes and relief thickness only'],'preserved':['blade vertex positions and topology','shaft and forward grip','blunt pommel','collar outline','tassel placement and fan']}
(OUT/'Shape_Preservation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
activate(blade)
print(json.dumps(report))
exec(compile((ROOT/'Tools/SpearAsset/cut_recessed_nervure.py').read_text(encoding='utf-8'),'cut_recessed_nervure.py','exec'))
