"""MCP entry point: repack only the untouched rosewood shaft into four columns.

Adds exactly three 32-vertex rings on existing straight edges. Original vertex
coordinates, face winding and loop normals are retained; new normals interpolate
the original face corners. No texture, other component, save, export or render
operations. Parent runs this through its Blender MCP session.
"""
import bisect
import collections
import hashlib
import json
import math
import struct
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy')
OUT = ROOT/'Saved/Diagnostics/ImperialSpear/HandleFinish'
NAME = '01 \u2022 rosewood shaft.001'
ART = 'SPEAR \u2022 editable components'
UV_NAME = 'UV0_SurfaceAtlas'
OLD_Z = [.09, .15, .55, 1.12, 1.48, 1.66]
CUTS = [.4825, .875, 1.2675]
QUARTERS = [.09, *CUTS, 1.66]
SIDES = 32
ATLAS = 4096
GUTTER = 8
ACTIVE_U = 496
ACTIVE_V = 2032


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(',', ':')).encode()).hexdigest()


def float32(value):
    return struct.unpack('f',struct.pack('f',value))[0]


def snapshot(ob):
    mesh=ob.data
    return {'geometry':digest({'vertices':[list(v.co) for v in mesh.vertices],
                               'faces':[list(p.vertices) for p in mesh.polygons]}),
            'uv':{layer.name:digest([list(t.uv) for t in layer.data]) for layer in mesh.uv_layers},
            'normals':digest([list(n.vector) for n in mesh.corner_normals]),
            'materials':[m.name if m else None for m in mesh.materials],
            'material_indices':[p.material_index for p in mesh.polygons],
            'matrix':[list(row) for row in ob.matrix_world],
            'modifiers':[(m.name,m.type) for m in ob.modifiers]}


def canonical_z(value):
    for z in QUARTERS:
        if abs(value-z)<1e-6:return z
    return value


art=bpy.data.collections[ART]
objects={ob.name:ob for ob in art.objects if ob.type=='MESH'}
assert NAME in objects
ob=objects[NAME]
source=ob.data
assert source.users==1,('Shared shaft data',source.users)
assert not ob.vertex_groups,'Unexpected shaft vertex groups'
assert source.shape_keys is None,'Unexpected shaft shape keys'
assert [layer.name for layer in source.uv_layers]==[UV_NAME]
before={name:snapshot(obj) for name,obj in objects.items()}
probe=json.loads((OUT/'Handle_Probe.json').read_text(encoding='utf-8'))['objects'][NAME]
assert before[NAME]['geometry']==digest({'vertices':probe['vertices'],'faces':probe['faces']}), 'Shaft no longer matches accepted six-ring profile'
assert len(source.vertices)==192 and len(source.polygons)==162
source_vertices=[list(v.co) for v in source.vertices]
source_faces=[list(p.vertices) for p in source.polygons]
source_normals=[Vector(n.vector) for n in source.corner_normals]
source_uv=[list(item.uv) for item in source.uv_layers[UV_NAME].data]
source_edge_state={tuple(sorted(e.vertices)):{'use_seam':e.use_seam,
                   'use_edge_sharp':getattr(e,'use_edge_sharp',False)} for e in source.edges}
for ring,z in enumerate(OLD_Z):
    for j in range(SIDES):
        v=source_vertices[ring*SIDES+j]
        assert abs(v[2]-z)<1e-6,('Unexpected ring order',ring,j,v)
        angle=math.atan2(v[1],v[0])%math.tau
        expected=math.tau*j/SIDES
        assert abs((angle-expected+math.pi)%math.tau-math.pi)<2e-6
for band in range(5):
    for j in range(SIDES):
        expected=[band*SIDES+j,band*SIDES+(j+1)%SIDES,
                  (band+1)*SIDES+(j+1)%SIDES,(band+1)*SIDES+j]
        assert source_faces[band*SIDES+j]==expected,('Unexpected shaft winding',band,j)
assert source_faces[-2]==list(range(31,-1,-1))
assert source_faces[-1]==list(range(160,192))

vertices=[v[:] for v in source_vertices]
new_rings={}
new_vertex_sources={}
max_interpolation_error=0.
for z in CUTS:
    low=bisect.bisect_right(OLD_Z,z)-1
    base=len(vertices);new_rings[z]=base
    for j in range(SIDES):
        a,b=low*SIDES+j,(low+1)*SIDES+j
        va,vb=source_vertices[a],source_vertices[b]
        t=(z-va[2])/(vb[2]-va[2])
        exact=[aa+(bb-aa)*t for aa,bb in zip(va,vb)]
        value=[float32(c) for c in exact]
        vertices.append(value);new_vertex_sources[base+j]=(a,b,t)
        max_interpolation_error=max(max_interpolation_error,math.sqrt(sum((a-b)**2 for a,b in zip(value,exact))))
assert len(vertices)==288 and vertices[:192]==source_vertices
assert max_interpolation_error<2e-7

side_uv=[source_uv[li][0] for p in source.polygons[:160] for li in p.loop_indices]
u_min,u_max=min(side_uv),max(side_uv)
assert abs(u_min-.003)<1e-6 and abs(u_max-.497)<1e-6
faces=[];uv_loops=[];normal_loops=[];smooth=[];material_ids=[];face_columns=[]
old_normal_checks=[];new_normal_checks=[]
face_source=[]

def side_uv_at(u,z,column):
    local=(canonical_z(z)-QUARTERS[3-column])/(QUARTERS[4-column]-QUARTERS[3-column])
    assert -1e-6<=local<=1+1e-6,(z,column,local)
    local=max(0.,min(1.,local))
    u=max(0.,min(1.,u))
    px=column*512+GUTTER+ACTIVE_U*u
    py=2048+GUTTER+(1-local)*ACTIVE_V
    return [float32(px/ATLAS),float32((ATLAS-py)/ATLAS)]

for pi,polygon in enumerate(source.polygons[:160]):
    f=list(polygon.vertices)
    lis=list(polygon.loop_indices)
    lower,upper=source_vertices[f[0]][2],source_vertices[f[2]][2]
    interior=[z for z in CUTS if lower+1e-6<z<upper-1e-6]
    levels=[lower,*interior,upper]
    j=f[0]%SIDES
    ua=(source_uv[lis[0]][0]-u_min)/(u_max-u_min)
    ub=(source_uv[lis[1]][0]-u_min)/(u_max-u_min)
    assert abs(ua-j/SIDES)<1e-6 and abs(ub-(j+1)/SIDES)<1e-6
    def at(z,right):
        if abs(z-lower)<1e-7:
            local=1 if right else 0
            return f[local],source_normals[lis[local]].copy(),True
        if abs(z-upper)<1e-7:
            local=2 if right else 3
            return f[local],source_normals[lis[local]].copy(),True
        vi=new_rings[z]+((j+1)%SIDES if right else j)
        t=(z-lower)/(upper-lower)
        lo,hi=(1,2) if right else (0,3)
        n=source_normals[lis[lo]].lerp(source_normals[lis[hi]],t).normalized()
        return vi,n,False
    for a,b in zip(levels,levels[1:]):
        column=3-(bisect.bisect_right(QUARTERS,(a+b)*.5)-1)
        corners=[at(a,False),at(a,True),at(b,True),at(b,False)]
        faces.append([c[0] for c in corners]);face_source.append(pi)
        smooth.append(polygon.use_smooth);material_ids.append(polygon.material_index);face_columns.append(column)
        for (vi,n,original),u,z in zip(corners,(ua,ub,ub,ua),(a,a,b,b)):
            uv_loops.append(side_uv_at(u,z,column))
            normal_loops.append(tuple(n))
            (old_normal_checks if original else new_normal_checks).append((len(normal_loops)-1,tuple(n)))

# Reuse very small, separate cap islands entirely inside the left tile gutter.
for pi in (160,161):
    polygon=source.polygons[pi];f=list(polygon.vertices)
    faces.append(f);face_source.append(pi);face_columns.append(None)
    smooth.append(polygon.use_smooth);material_ids.append(polygon.material_index)
    center_y=4092 if pi==160 else 2052
    for vi,li in zip(f,polygon.loop_indices):
        v=Vector(source_vertices[vi]);radius=math.hypot(v.x,v.y)
        px=4+2*v.x/radius;py=center_y+2*v.y/radius
        uv_loops.append([float32(px/ATLAS),float32((ATLAS-py)/ATLAS)])
        normal_loops.append(tuple(source_normals[li]))
        old_normal_checks.append((len(normal_loops)-1,tuple(source_normals[li])))

old_triangles=sum(len(f)-2 for f in source_faces)
new_triangles=sum(len(f)-2 for f in faces)
assert len(faces)==258 and old_triangles==380 and new_triangles==572
assert len(uv_loops)==len(normal_loops)==sum(len(f) for f in faces)
edge_counts=collections.Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f,f[1:]+f[:1]))
assert all(count==2 for count in edge_counts.values()),'Repacked shaft is not closed'
edge_directions=collections.Counter((a,b) for f in faces for a,b in zip(f,f[1:]+f[:1]))
assert all(edge_directions[(a,b)]==edge_directions[(b,a)] for a,b in edge_directions), 'Face winding changed'
minimum_normal_dot=1.;maximum_plane_error=0.;offset=0;volume=0.
columns={i:[] for i in range(4)}
for fi,f in enumerate(faces):
    coords=[Vector(vertices[vi]) for vi in f]
    if face_columns[fi] is not None:
        src=[Vector(source_vertices[vi]) for vi in source_faces[face_source[fi]]]
        plane=(src[1]-src[0]).cross(src[2]-src[0]).normalized()
        maximum_plane_error=max(maximum_plane_error,max(abs((v-src[0]).dot(plane)) for v in coords))
        columns[face_columns[fi]].extend(uv_loops[offset:offset+len(f)])
    for j in range(1,len(f)-1):
        a,b,c=coords[0],coords[j],coords[j+1]
        n=(b-a).cross(c-a);assert n.length>1e-12
        volume+=a.dot(b.cross(c))/6
        n.normalize()
        for corner in (0,j,j+1):
            minimum_normal_dot=min(minimum_normal_dot,n.dot(Vector(normal_loops[offset+corner])))
    offset+=len(f)
assert volume>0 and minimum_normal_dot>.9
assert maximum_plane_error<2e-7
column_reports=[]
for column,values in columns.items():
    xs=[uv[0]*ATLAS for uv in values];ys=[ATLAS-uv[1]*ATLAS for uv in values]
    expected=[column*512+8,2056,column*512+504,4088]
    actual=[min(xs),min(ys),max(xs),max(ys)]
    assert max(abs(a-b) for a,b in zip(actual,expected))<.001,(column,actual,expected)
    assert min(xs)-column*512>=8-.001 and (column+1)*512-max(xs)>=8-.001
    assert min(ys)-2048>=8-.001 and 4096-max(ys)>=8-.001
    column_reports.append({'column':column,'z_bottom_top_m':[QUARTERS[3-column],QUARTERS[4-column]],
                           'active_bounds_png_xyxy':actual})

mesh=bpy.data.meshes.new(source.name+' Four wood strips')
try:
    mesh.from_pydata(vertices,[],faces);mesh.update()
    for material in source.materials:mesh.materials.append(material)
    for key in source.keys():mesh[key]=source[key]
    uv=mesh.uv_layers.new(name=UV_NAME);uv.active_render=True
    for dst,value in zip(uv.data,uv_loops):dst.uv=value
    for p,flag,material in zip(mesh.polygons,smooth,material_ids):
        p.use_smooth=flag;p.material_index=material
    for edge in mesh.edges:
        a,b=edge.vertices;key=tuple(sorted((a,b)))
        state=source_edge_state.get(key)
        if state is None:
            supports=[]
            for vi in (a,b):
                supports.append(set(new_vertex_sources[vi][:2]) if vi in new_vertex_sources else {vi})
            support=set.union(*supports)
            if len(support)==2:state=source_edge_state.get(tuple(sorted(support)))
        if state:
            edge.use_seam=state['use_seam']
            if hasattr(edge,'use_edge_sharp'):edge.use_edge_sharp=state['use_edge_sharp']
        if abs(vertices[a][2]-vertices[b][2])<1e-7 and any(abs(vertices[a][2]-z)<1e-6 for z in CUTS):
            edge.use_seam=True
    mesh.normals_split_custom_set(normal_loops);mesh.update()
    actual_normals=[Vector(n.vector) for n in mesh.corner_normals]
    assert all(.999<n.length<1.001 for n in actual_normals)
    def max_angle(checks):
        return max(math.degrees(actual_normals[li].angle(Vector(n),0.)) for li,n in checks)
    original_normal_angle=max_angle(old_normal_checks)
    interpolated_normal_angle=max_angle(new_normal_checks)
    assert max(original_normal_angle,interpolated_normal_angle)<.1
    assert [list(v.co) for v in mesh.vertices[:192]]==source_vertices
    ob.data=mesh
    bpy.context.view_layer.update()
    after={name:snapshot(obj) for name,obj in objects.items()}
    for name in before:
        if name!=NAME:assert before[name]==after[name],('Protected component changed',name)
    for key in ('materials','matrix','modifiers'):
        assert before[NAME][key]==after[NAME][key],('Shaft protected property changed',key)
    assert len(mesh.vertices)==288 and sum(len(p.vertices)-2 for p in mesh.polygons)==572
    assert digest([list(item.uv) for item in mesh.uv_layers[UV_NAME].data])==digest(uv_loops)
    circumferences=[]
    for r in range(6):
        ring=[Vector(v) for v in source_vertices[r*32:(r+1)*32]]
        circumferences.append(sum((ring[(j+1)%32]-ring[j]).length for j in range(32)))
    densities=[ACTIVE_U/(c*1000) for c in circumferences]
    report={'object':NAME,'old_vertices':192,'new_vertices':288,'added_vertices':96,
            'old_triangles':old_triangles,'new_triangles':new_triangles,'added_triangles':192,
            'old_rings':6,'new_rings':9,'added_ring_z_m':CUTS,
            'protected_components_identical':len(before)-1,'original_vertices_unchanged':True,
            'maximum_interpolation_error_m':max_interpolation_error,
            'maximum_original_face_plane_error_m':maximum_plane_error,
            'minimum_triangle_corner_normal_dot':minimum_normal_dot,
            'maximum_original_normal_angle_error_degrees':original_normal_angle,
            'maximum_interpolated_normal_angle_error_degrees':interpolated_normal_angle,
            'closed_manifold':True,'positive_volume_m3':volume,
            'atlas':{'atlas_size_px':ATLAS,'wood_tile_png_xyxy':[0,2048,2048,4096],
                     'columns':4,'gutter_px':GUTTER,'active_column_width_px':ACTIVE_U,
                     'active_column_height_px':ACTIVE_V},
            'density':{'axial_px_per_mm':ACTIVE_V/((QUARTERS[1]-QUARTERS[0])*1000),
                       'circumferential_px_per_mm_min':min(densities),
                       'circumferential_px_per_mm_max':max(densities)},
            'seam_padding_passed':True,'columns':column_reports,
            'cap_islands':'2-pixel radius, centered at PNG (4,4092) and (4,2052), wholly in gutter',
            'old_geometry_sha256':before[NAME]['geometry'],'new_geometry_sha256':after[NAME]['geometry'],
            'new_uv_sha256':after[NAME]['uv'][UV_NAME]}
    (OUT/'Wood_UV_Repack_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
except Exception:
    ob.data=source
    if mesh.users==0:bpy.data.meshes.remove(mesh)
    raise
else:
    source.use_fake_user=True
    source.name='Before four-column wood UV '+source.name
print(json.dumps(report))
