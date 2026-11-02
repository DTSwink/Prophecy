"""Validate the final handle/S exception against the user-accepted head checkpoint."""
import bpy,bmesh,json,hashlib,math,bisect,struct
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');WORK=ROOT/'Saved/Diagnostics/ImperialSpear/HandleFinish';OUT=ROOT/'Exports/ImperialSpear'
art=bpy.data.collections['SPEAR • editable components'];base=json.loads((WORK/'Accepted_Baseline.json').read_text(encoding='utf-8'))
allowed=('03 •','04 •','Grip •','Socket • continuous cast inverted S')
SHAFT='01 • rosewood shaft.001'
def is_allowed(name):return name==SHAFT or name.startswith(allowed)
objects={o.name:o for o in art.objects if o.type=='MESH'}
def digest(value):return hashlib.sha256(json.dumps(value,separators=(',',':')).encode()).hexdigest()
def values(o):return {'geometry':digest({'vertices':[list(v.co) for v in o.data.vertices],'faces':[list(p.vertices) for p in o.data.polygons]}),
                      'uv':digest([list(v.uv) for v in o.data.uv_layers['UV0_SurfaceAtlas'].data])}
protected={}
for name,prior in base.items():
    if is_allowed(name):continue
    assert name in objects,('Protected object removed',name)
    now=values(objects[name]);assert now==prior,('Protected accepted component altered',name)
    protected[name]=True
assert len(protected)==80,('Unexpected protected component count',len(protected))
assert all(name in base or is_allowed(name) for name in objects)
assert all(math.isfinite(c) for o in objects.values() for v in o.data.vertices for c in v.co)
assert not any(name.startswith('TEMP') for name in objects)
components={}
for name,ob in objects.items():
    if not is_allowed(name):continue
    mesh=ob.data;bm=bmesh.new();bm.from_mesh(mesh)
    closed=all(e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True);bm.free()
    assert closed and volume>0,(name,closed,volume)
    assert len(mesh.uv_layers)==1 and mesh.uv_layers[0].name=='UV0_SurfaceAtlas'
    dots=[p.normal.dot(mesh.corner_normals[i].vector) for p in mesh.polygons for i in p.loop_indices]
    assert min(dots)>0,(name,min(dots))
    components[name]={'closed':closed,'volume_m3':volume,'triangles':sum(len(p.vertices)-2 for p in mesh.polygons),
                      'minimum_corner_face_normal_dot':min(dots)}


def audit_shaft_repack():
    """Prove the one shaft exception is only three linear cross-sections + UVs."""
    path=WORK/'Wood_UV_Repack_Verification.json'
    raw=path.read_bytes();record=json.loads(raw)
    assert record['object']==SHAFT
    now=values(objects[SHAFT])
    assert record['old_geometry_sha256']==base[SHAFT]['geometry']
    assert record['new_geometry_sha256']==now['geometry']
    assert record['new_uv_sha256']==now['uv']
    assert record['original_vertices_unchanged'] and record['seam_padding_passed']
    assert record['added_vertices']==96 and record['added_triangles']==192
    assert record['added_ring_z_m']==[.4825,.875,1.2675]
    source=json.loads((WORK/'Handle_Probe.json').read_text(encoding='utf-8'))['objects'][SHAFT]
    prior=source['vertices'];prior_faces=source['faces']
    assert digest({'vertices':prior,'faces':prior_faces})==base[SHAFT]['geometry']
    mesh=objects[SHAFT].data;actual=[list(v.co) for v in mesh.vertices]
    actual_faces=[list(p.vertices) for p in mesh.polygons]
    assert len(actual)==288 and len(actual_faces)==258
    assert actual[:192]==prior
    cuts=[.4825,.875,1.2675];old_z=[.09,.15,.55,1.12,1.48,1.66]
    quarters=[.09,*cuts,1.66]
    def f32(x):return struct.unpack('f',struct.pack('f',x))[0]
    expected=[v[:] for v in prior];rings={};interpolation_error=0.
    for z in cuts:
        band=bisect.bisect_right(old_z,z)-1;rings[z]=len(expected)
        for j in range(32):
            a,b=prior[band*32+j],prior[(band+1)*32+j]
            t=(z-a[2])/(b[2]-a[2]);exact=[x+(y-x)*t for x,y in zip(a,b)]
            value=[f32(x) for x in exact];expected.append(value)
            interpolation_error=max(interpolation_error,math.sqrt(sum((x-y)**2 for x,y in zip(value,exact))))
    assert actual==expected,'Shaft differs from exact three-ring linear refinement'
    assert interpolation_error<5e-8
    # The original mesh is retained by the repacker. Recompute expected normals
    # from that source; the application report alone is not the normal proof.
    retained=[]
    for candidate in bpy.data.meshes:
        if not candidate.name.startswith('Before four-column wood UV '):continue
        value={'vertices':[list(v.co) for v in candidate.vertices],
               'faces':[list(p.vertices) for p in candidate.polygons]}
        if digest(value)==base[SHAFT]['geometry']:retained.append(candidate)
    assert len(retained)==1,('Expected one retained accepted shaft',len(retained))
    retained=retained[0]
    old_normals=[Vector(n.vector) for n in retained.corner_normals]
    new_normals=[Vector(n.vector) for n in mesh.corner_normals]
    uvs=[list(item.uv) for item in mesh.uv_layers['UV0_SurfaceAtlas'].data]
    rebuilt_faces=[];max_normal_angle=0.;max_plane_error=0.;max_uv_error_px=0.
    column_bounds={c:[] for c in range(4)};offset=0
    for pi,face in enumerate(prior_faces[:160]):
        lo,hi=prior[face[0]][2],prior[face[2]][2]
        levels=[lo,*[z for z in cuts if lo+1e-6<z<hi-1e-6],hi]
        j=face[0]%32;lis=list(retained.polygons[pi].loop_indices)
        p0,p1,p2=[Vector(prior[i]) for i in face[:3]]
        plane=(p1-p0).cross(p2-p0).normalized()
        def at(z,right):
            if abs(z-lo)<1e-7:
                k=1 if right else 0;return face[k],old_normals[lis[k]].copy()
            if abs(z-hi)<1e-7:
                k=2 if right else 3;return face[k],old_normals[lis[k]].copy()
            vi=rings[z]+((j+1)%32 if right else j);t=(z-lo)/(hi-lo)
            a,b=(1,2) if right else (0,3)
            return vi,old_normals[lis[a]].lerp(old_normals[lis[b]],t).normalized()
        for a,b in zip(levels,levels[1:]):
            column=3-(bisect.bisect_right(quarters,(a+b)*.5)-1)
            corners=[at(a,False),at(a,True),at(b,True),at(b,False)]
            rebuilt_faces.append([vi for vi,_ in corners])
            for (vi,n),angle,z in zip(corners,(j/32,(j+1)/32,(j+1)/32,j/32),(a,a,b,b)):
                max_plane_error=max(max_plane_error,abs((Vector(actual[vi])-p0).dot(plane)))
                max_normal_angle=max(max_normal_angle,math.degrees(new_normals[offset].angle(n,0.)))
                for bound in quarters:
                    if abs(z-bound)<1e-6:z=bound;break
                local=(z-quarters[3-column])/(quarters[4-column]-quarters[3-column])
                target=[column*512+8+496*angle,2056+(1-local)*2032]
                pixel=[uvs[offset][0]*4096,4096-uvs[offset][1]*4096]
                max_uv_error_px=max(max_uv_error_px,max(abs(x-y) for x,y in zip(pixel,target)))
                column_bounds[column].append(pixel);offset+=1
    for pi in (160,161):
        rebuilt_faces.append(prior_faces[pi])
        for li in retained.polygons[pi].loop_indices:
            max_normal_angle=max(max_normal_angle,math.degrees(new_normals[offset].angle(old_normals[li],0.)))
            pixel=[uvs[offset][0]*4096,4096-uvs[offset][1]*4096]
            assert 2-.001<=pixel[0]<=6+.001
            assert (4090-.001<=pixel[1]<=4094+.001) if pi==160 else (2050-.001<=pixel[1]<=2054+.001)
            offset+=1
    assert actual_faces==rebuilt_faces,'Shaft winding or split faces differ from expected refinement'
    assert offset==len(uvs)==len(new_normals)
    assert max_normal_angle<.1 and max_plane_error<2e-7 and max_uv_error_px<.001
    for col,points in column_bounds.items():
        bounds=[min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
        target=[col*512+8,2056,col*512+504,4088]
        assert max(abs(a-b) for a,b in zip(bounds,target))<.001
    return {'status':'THREE_LINEAR_RINGS_AND_FOUR_UV_STRIPS_PROVED',
            'repack_report':'Wood_UV_Repack_Verification.json','repack_report_sha256':hashlib.sha256(raw).hexdigest(),
            'geometry_sha256':now['geometry'],'uv_sha256':now['uv'],
            'original_vertices_identical':192,'added_vertices':96,'added_triangles':192,
            'added_ring_z_m':cuts,'maximum_interpolation_error_m':interpolation_error,
            'maximum_original_face_plane_error_m':max_plane_error,
            'maximum_loop_normal_angle_error_degrees':max_normal_angle,
            'maximum_uv_formula_error_px':max_uv_error_px,'eight_pixel_gutters_proved':True,
            'density':record['density']}


shaft_repack=audit_shaft_repack()
report={'status':'HANDLE_AND_ANGULAR_S_SOURCE_AUDITED','source_objects':len(objects),
        'source_triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects.values()),
        'allowed_geometry_changes':list(allowed)+[SHAFT],'protected_component_count':len(protected),
        'protected_geometry_and_uv_checks':protected,'components':components,
        'accepted_blade_and_all_other_head_parts_unchanged':True,
        'shaft_uv_repack':shaft_repack,
        'texture_protection_report':'Handle_Texture_Application.json','unreal_validated':False}
(OUT/'Handle_Finish_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='protected_geometry_and_uv_checks'}))
