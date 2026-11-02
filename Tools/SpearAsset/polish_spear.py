"""Final sculptural refinement, keeping the existing editable asset."""
import bpy,bmesh,math
from mathutils import Vector
col=bpy.data.collections['SPEAR • editable components']
ob=next(o for o in col.objects if o.name.startswith('07 •'))
mat=ob.data.materials[0]
# A gently crowned cast plate with a shaped lower spur and fine perimeter bead.
outline=[(-.010,1.718),(-.021,1.726),(-.038,1.710),(-.044,1.733),(-.047,1.757),
         (-.041,1.777),(-.033,1.797),(-.022,1.807),(-.006,1.802),(.007,1.790),
         (.026,1.800),(.043,1.797),(.049,1.787),(.041,1.779),(.030,1.779),
         (.024,1.757),(.014,1.739),(.020,1.724),(.008,1.718)]
# Preserve intentional terminal points while softening other contour corners.
rim=[]
for i,(x,z) in enumerate(outline):
    before=Vector(outline[(i-1)%len(outline)]); point=Vector((x,z)); after=Vector(outline[(i+1)%len(outline)])
    if i in [2,8,9,14]: rim.append((x,z)); continue
    a=point+(before-point)*.12; b=point+(after-point)*.12
    for t in [0,.5,1]:
        v=(1-t)**2*a+2*(1-t)*t*point+t*t*b; rim.append(tuple(v))
n=len(rim); verts=[]
for side,scale,y in [(-1,.78,.0285),(-1,1,.020),(1,1,.020),(1,.78,.0285)]:
    for x,z in rim: verts.append((x*scale,side*y,1.758+(z-1.758)*scale))
faces=[tuple(reversed(range(n))),tuple(3*n+i for i in range(n))]
for ring in range(3):
    for i in range(n): faces.append((ring*n+i,ring*n+(i+1)%n,(ring+1)*n+(i+1)%n,(ring+1)*n+i))
data=bpy.data.meshes.new('Crowned gold palmette'); data.from_pydata(verts,[],faces); data.materials.append(mat); data.update()
bm=bmesh.new(); bm.from_mesh(data); bmesh.ops.recalc_face_normals(bm,faces=bm.faces); bm.to_mesh(data); bm.free()
uv=data.uv_layers.new(name='UV0_SurfaceAtlas')
for p in data.polygons:
    p.use_smooth=p.index>1
    for li in p.loop_indices:
        v=data.vertices[data.loops[li].vertex_index].co
        uv.data[li].uv=(.503+(v.x+.05)*4.85,.503+(v.z-1.70)*4.4)
ob.data=data
# Raise relief to sit on the cast face; the engraving remains crisp and legible.
for o in col.objects:
    if o.name.startswith(('Socket • raised S','Socket • sweeping lower')):
        for v in o.data.vertices: v.co.y+=math.copysign(.0035,v.co.y)
# Silk underlay between the independent fine edge strands, with physical folds.
verts=[]; faces=[]; countu=12; countv=14
for side in [-1,1]:
    for j in range(countv+1):
        t=j/countv
        for i in range(countu+1):
            f=i/countu-.5
            endx=.225+f*.05; endz=1.550+f*.038+.002*math.sin(i*2.3)
            x=.130+(endx-.130)*t
            z=1.697+(endz-1.697)*t+.009*math.sin(t*math.pi)
            y=-.006+math.sin(f*math.pi*9)*.0028*t+side*.00018
            verts.append((x,y,z))
row=countu+1; layer=row*(countv+1)
for k in range(2):
    for j in range(countv):
        for i in range(countu):
            a=k*layer+j*row+i; faces.append((a,a+1,a+row+1,a+row) if k==0 else (a+row,a+row+1,a+1,a))
data=bpy.data.meshes.new('Silk ribbon fan'); data.from_pydata(verts,[],faces); data.materials.append(mat); data.update()
bm=bmesh.new(); bm.from_mesh(data)
# The taper's zero-width first row is welded to eliminate collapsed triangles.
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
bmesh.ops.recalc_face_normals(bm,faces=bm.faces); bm.to_mesh(data); bm.free()
uv=data.uv_layers.new(name='UV0_SurfaceAtlas')
for p in data.polygons:
    p.use_smooth=True
    for li in p.loop_indices:
        v=data.vertices[data.loops[li].vertex_index].co
        uv.data[li].uv=(.753+max(0,min(1,(v.x-.13)/.12))*.244,.003+max(0,min(1,(v.z-1.52)/.18))*.494)
o=bpy.data.objects.new('Tassel • woven silk fan',data); col.objects.link(o)
print('Crowned cast plate and woven silk fan refined')
