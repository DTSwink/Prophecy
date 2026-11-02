"""Offline clean angular relief from the current accepted S mesh probe.

No bpy import or live scene access. The projected exterior stays aligned while
constrained triangulation removes inherited folds at the two tight curls.
Run with the task Python to write Angular_S_Relief.json for the guarded importer.
"""
from pathlib import Path
import collections
import hashlib
import json
import math
import struct
import itertools
import numpy as np
from shapely import constrained_delaunay_triangles
from shapely.geometry import Point, Polygon
from shapely.geometry.polygon import orient

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Saved/Diagnostics/ImperialSpear/HandleFinish'
PREFIX = 'Socket \u2022 continuous cast inverted S'


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(',', ':')).encode()).hexdigest()


def f32(value):
    return struct.unpack('f', struct.pack('f', value))[0]


def sub(a, b):
    return [x-y for x, y in zip(a, b)]


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def unit(v):
    length = math.sqrt(dot(v, v))
    assert length > 1e-15
    return [x/length for x in v]


def triangles(face):
    return [(face[0], face[i], face[i+1]) for i in range(1, len(face)-1)]


def possible_triangles(face):
    # Audit both possible diagonals: Blender may choose either for a quad.
    if len(face) == 4:
        a,b,c,d = face
        return [(a,b,c),(a,c,d),(a,b,d),(b,c,d)]
    return triangles(face)


def compatible_normal(preferred, constraints):
    if min(dot(preferred, n) for n in constraints) >= .55:
        return preferred, False
    candidates = constraints[:]
    for a,b in itertools.combinations(constraints, 2):
        s = [x+y for x,y in zip(a,b)]
        if dot(s,s) > 1e-20:
            candidates.append(unit(s))
    for a,b,c in itertools.combinations(constraints, 3):
        n = cross(sub(a,b), sub(a,c))
        if dot(n,n) > 1e-20:
            n = unit(n)
            candidates.extend((n, [-v for v in n]))
    return max(candidates, key=lambda n: min(dot(n,c) for c in constraints)), True


def generate_swept_proposal(name, source):
    old = source['vertices']
    faces = source['faces']
    assert len(old) == 909 and len(faces) == 902
    vertices = [v[:] for v in old]
    side = 1 if old[0][1] > 0 else -1
    section_report = []
    for row in range(101):
        start = row*9
        a, b = old[start], old[start+6]
        width = math.hypot(b[0]-a[0], b[2]-a[2])
        base = (abs(a[1])+abs(b[1]))*.5
        old_height = abs(old[start+3][1])-base
        # Narrow ends must fade into a chased ridge, not remain tall wire tips.
        height = min(old_height, .32*width)
        for col, t, h in ((1, .04, .14), (2, .34, 1), (3, .5, 1),
                          (4, .66, 1), (5, .96, .14)):
            p = [a[k] + (b[k]-a[k])*t for k in range(3)]
            if col == 3:
                p[0], p[2] = old[start+3][0], old[start+3][2]
            local_base = abs(a[1])*(1-t)+abs(b[1])*t
            p[1] = side*(local_base+height*h)
            vertices[start+col] = [f32(c) for c in p]
        section_report.append({'row': row, 'width_mm': width*1000,
                               'height_mm': height*1000,
                               'flank_degrees': math.degrees(math.atan2(height*.86, width*.30))})
    # No index changes; foot edges and underside are exact original coordinates.
    preserved = [r*9+c for r in range(101) for c in (0, 6, 7, 8)]
    assert all(vertices[i] == old[i] for i in preserved)
    assert all(vertices[r*9+3][k] == old[r*9+3][k] for r in range(101) for k in (0, 2))
    assert all(math.isfinite(c) for v in vertices for c in v)
    edges = collections.Counter(tuple(sorted((a, b))) for f in faces for a, b in zip(f, f[1:]+f[:1]))
    assert all(v == 2 for v in edges.values()), 'Relief is not manifold'

    # Smooth longitudinally only. Crest halves share one group; every inclined
    # face has its own group, preventing the broad facets from shading as a tube.
    face_vectors = []
    face_groups = []
    groups = collections.defaultdict(lambda: [0., 0., 0.])
    min_area = float('inf')
    min_quad_triangle_alignment = 1.
    folded_faces = []
    inherited_folded_faces = []
    volume = 0.
    for fi, face in enumerate(faces):
        vectors = []
        for aa, bb, cc in triangles(face):
            va, vb, vc = vertices[aa], vertices[bb], vertices[cc]
            n = cross(sub(vb, va), sub(vc, va))
            area2 = math.sqrt(dot(n, n))
            assert area2 > 1e-13, (name, fi, 'Degenerate triangle')
            min_area = min(min_area, area2*.5)
            volume += dot(va, cross(vb, vc))/6
            vectors.append(n)
        n = [sum(v[k] for v in vectors) for k in range(3)]
        face_vectors.append(n)
        if len(vectors) == 2:
            agreement = dot(unit(vectors[0]), unit(vectors[1]))
            min_quad_triangle_alignment = min(min_quad_triangle_alignment, agreement)
            if agreement < 0:
                folded_faces.append(fi)
            normals_old = [unit(cross(sub(old[b],old[a]),sub(old[c],old[a]))) for a,b,c in triangles(face)]
            if dot(*normals_old) < 0:
                inherited_folded_faces.append(fi)
        if fi < 900:
            j = fi % 9
            group = 'crest' if j in (2, 3) else 'section_'+str(j)
        else:
            group = 'cap_'+str(fi)
        face_groups.append(group)
        for vi in face:
            accum = groups[(group, vi)]
            for k in range(3):
                accum[k] += n[k]
    assert volume > 0, (name, 'Inward volume', volume)
    corner_normals = []
    min_dot = 1.
    worst = None
    group_dots = {}
    compatibility_corners = 0
    for fi, face in enumerate(faces):
        ns = []
        for vi in face:
            constraints = [unit(cross(sub(vertices[b],vertices[a]), sub(vertices[c],vertices[a])))
                           for a,b,c in possible_triangles(face) if vi in (a,b,c)]
            n, adjusted = compatible_normal(unit(groups[(face_groups[fi],vi)]), constraints)
            ns.append(n)
            compatibility_corners += int(adjusted)
        for tri in possible_triangles(face):
            geometric = unit(cross(sub(vertices[tri[1]], vertices[tri[0]]), sub(vertices[tri[2]], vertices[tri[0]])))
            for vi in tri:
                value = dot(geometric, ns[face.index(vi)])
                group_dots[face_groups[fi]] = min(group_dots.get(face_groups[fi], 1.), value)
                if value < min_dot:
                    min_dot = value
                    worst = (fi, face_groups[fi], vi, tri)
        corner_normals.append(ns)
    assert min_dot > 1e-6, (name, 'Backward or tangential corner normals', min_dot, worst, group_dots)
    report = {'vertices': len(vertices), 'polygons': len(faces),
              'triangles': sum(len(f)-2 for f in faces), 'manifold': True,
              'positive_volume_m3': volume, 'minimum_triangle_area_m2': min_area,
              'minimum_quad_triangle_normal_dot': min_quad_triangle_alignment,
              'minimum_triangle_corner_normal_dot': min_dot,
              'corner_normal_minimum_by_face_region': group_dots,
              'local_corner_compatibility_adjustments': compatibility_corners,
              'original_folded_quads': inherited_folded_faces,
              'candidate_folded_quads': folded_faces,
              'foot_and_back_vertices_unchanged': len(preserved),
              'centerline_xz_unchanged': True, 'topology_unchanged': True,
              'uv_data_unchanged_by_construction': True,
              'crest_fraction_of_footprint': .32,
              'section_samples': [section_report[i] for i in (0,25,50,75,100)]}
    return {'vertices': vertices, 'faces': faces, 'corner_normals': corner_normals,
            'face_regions': face_groups, 'source_geometry_sha256': digest({'vertices': old, 'faces': faces}),
            'source_uv_sha256': digest(source['uv']),
            'result_geometry_sha256': digest({'vertices': vertices, 'faces': faces}),
            'report': report}


def generate(name, source):
    """Retriangulate the actual footprint as a height field: no swept folds.

    The original narrow inner bends contain self-overlapping offset curves.
    Polygon cleaning resolves only their invisible interior overlap. All exposed
    boundary segments retain their original projected locations.
    """
    old = source['vertices']
    old_faces = source['faces']
    side = 1 if old[0][1] > 0 else -1
    rows = np.asarray(old, dtype=float).reshape(101,9,3)
    outer_coords = [tuple(rows[r,0,[0,2]]) for r in range(101)] + [tuple(rows[r,6,[0,2]]) for r in range(100,-1,-1)]
    raw_outer = Polygon(outer_coords)
    outer = orient(raw_outer.buffer(0), sign=1)
    assert outer.geom_type == 'Polygon' and outer.is_valid and not outer.interiors
    toe = orient(outer.buffer(-.00010, join_style='mitre').buffer(0), sign=1)
    assert toe.geom_type == 'Polygon' and toe.is_valid and not toe.interiors
    crest_coords = []
    for r in range(101):
        crest_coords.append(tuple(rows[r,0,[0,2]]*.66 + rows[r,6,[0,2]]*.34))
    for r in range(100,-1,-1):
        crest_coords.append(tuple(rows[r,0,[0,2]]*.34 + rows[r,6,[0,2]]*.66))
    crest = orient(Polygon(crest_coords).buffer(0).intersection(outer.buffer(-.00020,join_style='mitre')),sign=1)
    assert crest.geom_type == 'Polygon' and crest.is_valid and not crest.interiors
    assert toe.covers(crest) and outer.covers(toe)
    outer_coords = list(outer.exterior.coords)[:-1]
    centers = rows[:,3][:,[0,2]]
    widths = np.linalg.norm(rows[:,6][:,[0,2]]-rows[:,0][:,[0,2]],axis=1)
    heights = np.minimum(abs(rows[:,3,1])-.0125, .32*widths)
    assert heights.min() > .00025
    starts, vectors = centers[:-1], centers[1:]-centers[:-1]
    lengths2 = np.sum(vectors*vectors,axis=1)

    def height(p):
        p=np.asarray(p)
        ts=np.clip(np.sum((p-starts)*vectors,axis=1)/lengths2,0,1)
        d=np.sum((starts+vectors*ts[:,None]-p)**2,axis=1)
        i=int(np.argmin(d));t=ts[i]
        return float(heights[i]*(1-t)+heights[i+1]*t)

    # The relief was widened after its original UV projection. Interpolate its
    # actual loop UVs barycentrically instead of inventing an affine remapping.
    src_xyz=[];src_uv=[];offset=0
    for fi,f in enumerate(old_faces):
        if fi<900 and fi%9<6:
            for a,b,c in triangles(list(range(len(f)))):
                src_xyz.append([old[f[k]] for k in (a,b,c)])
                src_uv.append([source['uv'][offset+k] for k in (a,b,c)])
        offset+=len(f)
    src_xyz=np.asarray(src_xyz);src_uv=np.asarray(src_uv)
    src_xz=src_xyz[:,:,[0,2]]
    ab=src_xz[:,1]-src_xz[:,0];ac=src_xz[:,2]-src_xz[:,0]
    det=ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0]
    keep=abs(det)>1e-18
    src_xyz,src_uv,src_xz,ab,ac,det=[a[keep] for a in (src_xyz,src_uv,src_xz,ab,ac,det)]
    max_uv_projection_distance=0.
    def uv_at(p):
        nonlocal max_uv_projection_distance
        ap=np.asarray(p)-src_xz[:,0]
        b=(ap[:,0]*ac[:,1]-ap[:,1]*ac[:,0])/det
        c=(ab[:,0]*ap[:,1]-ab[:,1]*ap[:,0])/det
        weights=np.stack([1-b-c,b,c],axis=1)
        good=np.flatnonzero(np.min(weights,axis=1)>=-1e-6)
        if len(good):
            depths=np.sum(weights[good]*abs(src_xyz[good,:,1]),axis=1)
            i=good[int(np.argmax(depths))]
            return weights[i]@src_uv[i]
        best_distance=float('inf');best_uv=None
        for a,b in ((0,1),(1,2),(2,0)):
            starts=src_xz[:,a];vectors=src_xz[:,b]-starts
            ts=np.clip(np.sum((np.asarray(p)-starts)*vectors,axis=1)/np.sum(vectors*vectors,axis=1),0,1)
            distances=np.sum((starts+ts[:,None]*vectors-p)**2,axis=1)
            i=int(np.argmin(distances))
            if distances[i]<best_distance:
                best_distance=float(distances[i]);best_uv=src_uv[i,a]*(1-ts[i])+src_uv[i,b]*ts[i]
        distance=math.sqrt(best_distance)
        max_uv_projection_distance=max(max_uv_projection_distance,distance)
        assert distance<2e-7,('UV point outside source footprint',p,distance)
        return best_uv

    vertices=[];faces=[];regions=[];index={};uvs=[]
    def vertex(p,depth):
        xyz=(f32(p[0]),f32(side*depth),f32(p[1]))
        if xyz not in index:
            index[xyz]=len(vertices);vertices.append(list(xyz))
            uvs.append([f32(c) for c in uv_at((xyz[0],xyz[2]))])
        return index[xyz]

    def front_depth(p):
        point=Point(p)
        if outer.boundary.distance(point)<1e-10:return .0125
        if toe.boundary.distance(point)<1e-10:return .01260
        assert crest.boundary.distance(point)<1e-9 or crest.covers(point)
        return .0125+height(p)

    for region,polygon in (('toe',outer.difference(toe)), ('inclined',toe.difference(crest)), ('crest',crest)):
        assert polygon.geom_type=='Polygon' and polygon.is_valid
        covered=0.
        for tri in constrained_delaunay_triangles(polygon).geoms:
            assert polygon.covers(tri)
            covered+=tri.area
            coords=list(orient(tri,sign=1).exterior.coords)[:-1]
            f=[vertex(p,front_depth(p)) for p in coords]
            if side>0:f.reverse()
            faces.append(f);regions.append(region)
        assert abs(covered-polygon.area)<1e-12
    # Embedded flat back replaces the folded swept underside entirely.
    for tri in constrained_delaunay_triangles(outer).geoms:
        coords=list(orient(tri,sign=1).exterior.coords)[:-1]
        f=[vertex(p,.01225) for p in coords]
        if side<0:f.reverse()
        faces.append(f);regions.append('back')
    for i,a in enumerate(outer_coords):
        b=outer_coords[(i+1)%len(outer_coords)]
        fa,fb,ba,bb=vertex(a,.0125),vertex(b,.0125),vertex(a,.01225),vertex(b,.01225)
        for f in ([fa,fb,bb],[fa,bb,ba]):
            if side<0:f.reverse()
            faces.append(f);regions.append('embedded_wall')
    edges=collections.Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f,f[1:]+f[:1]))
    assert all(count==2 for count in edges.values()), ('Open mesh',name,[(k,v) for k,v in edges.items() if v!=2][:10])
    directed=collections.Counter((a,b) for f in faces for a,b in zip(f,f[1:]+f[:1]))
    assert all(directed[(a,b)]==directed[(b,a)] for a,b in directed), 'Inconsistent orientation'
    accum=collections.defaultdict(lambda: np.zeros(3))
    face_normals=[];areas=[];volume=0.
    min_front_y=1.
    for f,region in zip(faces,regions):
        va,vb,vc=[np.asarray(vertices[i]) for i in f]
        n=np.cross(vb-va,vc-va);length=float(np.linalg.norm(n))
        assert length>1e-14,('Degenerate',name,f)
        areas.append(length*.5);face_normals.append(n/length)
        volume+=float(np.dot(va,np.cross(vb,vc)))/6
        if region in ('toe','inclined','crest'):
            min_front_y=min(min_front_y,side*n[1]/length)
            assert side*n[1]>0,('Overturned visible triangle',name,f)
        for vi in f:accum[(region,vi)]+=n
    assert volume>0
    corner_normals=[];min_dot=1.;normal_adjustments=0
    for f,region,geometric in zip(faces,regions,face_normals):
        ns=[]
        for vi in f:
            n=accum[(region,vi)];n=n/np.linalg.norm(n)
            # Very tight curls can need a harder longitudinal corner. Keep the
            # true normal in its face hemisphere instead of concealing a fold.
            if float(np.dot(n,geometric))<.55:
                n=geometric.copy();normal_adjustments+=1
            min_dot=min(min_dot,float(np.dot(n,geometric)))
            ns.append(n.tolist())
        corner_normals.append(ns)
    assert min_dot>=.55-1e-8
    assert all(math.isfinite(c) for v in vertices for c in v)
    assert all(math.isfinite(c) for row in corner_normals for n in row for c in n)
    assert all(abs(sum(c*c for c in n)-1)<1e-10 for row in corner_normals for n in row)
    uv_loops=[uvs[i] for face in faces for i in face]
    raw_bounds=np.asarray(raw_outer.bounds);new_bounds=np.asarray(outer.bounds)
    assert float(np.max(abs(raw_bounds-new_bounds)))<1e-12
    report={'vertices':len(vertices),'triangles':len(faces),'manifold':True,
            'positive_volume_m3':volume,'minimum_triangle_area_m2':min(areas),
            'minimum_triangle_corner_normal_dot':min_dot,
            'minimum_visible_triangle_outward_y':min_front_y,
            'folded_visible_triangles':0,'degenerate_triangles':0,
            'footprint_bounds_unchanged':True,
            'footprint_overlap_cleaned_area_mm2':abs(raw_outer.area-outer.area)*1e6,
            'footprint_boundary_hausdorff_mm':raw_outer.boundary.hausdorff_distance(outer.boundary)*1000,
            'source_uv_interpolation_max_projection_distance_m':max_uv_projection_distance,
            'local_harder_normal_corners':normal_adjustments,
            'crest_fraction_of_width':.32,'toe_width_mm':.10,
            'topology_change':'Constrained triangulation removes three inherited folded quads per S; projected exterior follows the original footprint.',
            'source_vertices':len(old),'source_triangles':sum(len(f)-2 for f in old_faces),
            'back_embedded_depth_mm':.25}
    return {'vertices':vertices,'faces':faces,'corner_normals':corner_normals,
            'uv_loops':uv_loops,'face_regions':regions,
            'source_geometry_sha256':digest({'vertices':old,'faces':old_faces}),
            'source_uv_sha256':digest(source['uv']),
            'result_geometry_sha256':digest({'vertices':vertices,'faces':faces}),
            'report':report}


def main():
    probe = json.loads((OUT/'Handle_Probe.json').read_text(encoding='utf-8'))
    baseline = json.loads((OUT/'Accepted_Baseline.json').read_text(encoding='utf-8'))
    objects = {n: generate(n, s) for n, s in probe['objects'].items() if n.startswith(PREFIX)}
    assert len(objects) == 2
    for name, data in objects.items():
        assert data['source_geometry_sha256'] == baseline[name]['geometry']
        assert data['source_uv_sha256'] == baseline[name]['uv']
    payload = {'description': 'S relief only: flat 32% crest, broad inclined facets and 0.1 mm toe. Constrained triangulation removes inherited curl folds; UVs interpolate the original S. Hard cross-section joins with longitudinal smoothing.', 'objects': objects}
    path = OUT/'Angular_S_Relief.json'
    path.write_text(json.dumps(payload, separators=(',', ':')), encoding='utf-8')
    print(json.dumps({'path': str(path), 'objects': {n: d['report'] for n, d in objects.items()}}, indent=2))


if __name__ == '__main__':
    main()
