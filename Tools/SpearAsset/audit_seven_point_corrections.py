"""Measure the actual live correction meshes, including exported shading inputs."""
import bpy, bmesh, json, math, runpy
from pathlib import Path

ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy')
OUT=ROOT/'Exports/ImperialSpear'
art=bpy.data.collections['SPEAR • editable components']
runpy.run_path(str(ROOT/'Tools/SpearAsset/audit_reference_detail.py'))

def find(prefix):
    matches=[o for o in art.objects if o.name.startswith(prefix)]
    assert len(matches)==1,(prefix,[o.name for o in matches])
    return matches[0]

def inspect(ob,normal_check=False):
    mesh=ob.data
    bm=bmesh.new();bm.from_mesh(mesh)
    closed=all(e.is_manifold for e in bm.edges)
    volume=bm.calc_volume(signed=True);bm.free()
    assert closed and volume>0,(ob.name,closed,volume)
    row={'triangles':sum(len(p.vertices)-2 for p in mesh.polygons),
         'closed':closed,'volume_m3':volume,
         'bounds':{'min':[min(v.co[k] for v in mesh.vertices) for k in range(3)],
                   'max':[max(v.co[k] for v in mesh.vertices) for k in range(3)]}}
    if normal_check:
        values=[p.normal.dot(mesh.corner_normals[li].vector)
                for p in mesh.polygons for li in p.loop_indices]
        row['minimum_geometric_corner_normal_dot']=min(values)
        row['backward_corner_normals']=sum(d<-.001 for d in values)
        assert row['backward_corner_normals']==0,(ob.name,row)
    return row

body=find('07 •');crown=find('Blade • flame and compact unified')
sleeve=find('05 •');collar=find('Socket • thin flared neck ring')
ring=find('Socket • broad asymmetrical middle ring')
bead=find('Tassel • pierced small dark lacquer bead')
rows={o.name:inspect(o,o in (body,crown)) for o in (body,crown,sleeve,collar,ring,bead)}
sleeve_top=rows[sleeve.name]['bounds']['max'][2]
collar_top=rows[collar.name]['bounds']['max'][2]
seat_z=1.6684
assert sleeve_top<=seat_z-.0043,(sleeve_top,seat_z)
assert abs(collar_top-seat_z)<1e-6,(collar_top,seat_z)
assert list(collar.rotation_euler)==[0.0,0.0,0.0]
assert all(abs(c-1)<1e-7 for c in collar.scale)
assert bead.get('Reference_round_bead')
report={'components':rows,'sleeve_to_guard_axial_clearance_mm':(seat_z-sleeve_top)*1000,
        'collar_top_to_guard_seat_error_mm':abs(collar_top-seat_z)*1000,
        'collar_axis_aligned':True,'first_bead_round':True,
        'appearance_acceptance':'Requires visual review; numeric checks do not establish fidelity',
        'unreal_validated':False}
(OUT/'Seven_Point_Live_Audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
