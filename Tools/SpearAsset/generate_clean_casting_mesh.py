"""Generate explicit 45-degree casting chamfers without Blender or modifiers.

Run with the task mcp-env Python. Nested polygon strips are triangulated in XZ
instead of joining unrelated normalized-arc samples: this prevents crossing
quads at concave hooks and the narrow pierced-eye web.
"""

from collections import defaultdict, deque
from pathlib import Path
import json
import math

import mapbox_earcut
import numpy as np
from shapely import constrained_delaunay_triangles
from shapely.geometry import Point, Polygon
from shapely.geometry.polygon import orient


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'Saved/Diagnostics/ImperialSpear/ChamferCastingMesh.json'
AX, AY = .798, .603
NORM = math.hypot(AX, AY)
AX, AY = AX/NORM, AY/NORM
SCALE = .00096
OUTLINE = [(537,285),(550,279),(571,266),(590,267),(604,271),
           (612,277),(615,285),(613,296),(610,304),(615,313),
           (627,321),(619,333),(610,348),(602,362),(584,352),
           (573,347),(565,349),(560,355),(556,371),(548,362),
           (542,351),(539,335),(538,316)]


def ref(p):
    dx, dy = p[0]-172, p[1]-9
    return (dx*AY-dy*AX)*SCALE, 2.2-(dx*AX+dy*AY)*SCALE


def smooth_polygon(points, sharp=(10,13,18), samples=4):
    pts = np.asarray(points, dtype=np.float64)
    result = []
    for i, p in enumerate(pts):
        nxt, before, after = pts[(i+1)%len(pts)], pts[(i-1)%len(pts)], pts[(i+2)%len(pts)]
        t0 = np.zeros(2) if i in sharp else (nxt-before)*.18
        t1 = np.zeros(2) if (i+1)%len(pts) in sharp else (after-p)*.18
        for j in range(samples):
            t = j/samples
            result.append((1-t)**3*p + 3*(1-t)**2*t*(p+t0) +
                          3*(1-t)*t*t*(nxt-t1) + t**3*nxt)
    return [ref(p) for p in result]


def clean_contour(poly):
    """Remove redundant collinear points before earcut can drop them itself."""
    assert poly.geom_type == 'Polygon' and poly.is_valid and not poly.interiors
    coords = list(orient(poly, sign=1).exterior.coords)[:-1]
    changed = True
    while changed:
        changed = False
        cleaned = []
        for i, p in enumerate(coords):
            a, b = coords[i-1], coords[(i+1)%len(coords)]
            cross = (p[0]-a[0])*(b[1]-p[1])-(p[1]-a[1])*(b[0]-p[0])
            if abs(cross) < 1e-15:
                changed = True
            else:
                cleaned.append(p)
        coords = cleaned
        assert len(coords) >= 3
    return coords


def circle(center, radius, count=64):
    return [(center[0]+radius*math.cos(math.tau*j/count),
             center[1]+radius*math.sin(math.tau*j/count)) for j in range(count)]


def sample_eye_transition(coords, eye, maximum_step=.0005):
    """Resolve the locally varying rim height; preserve all contour edges."""
    result=[];center=np.asarray(eye)
    for i,a in enumerate(coords):
        a=np.asarray(a);b=np.asarray(coords[(i+1)%len(coords)])
        near=min(np.linalg.norm(a-center),np.linalg.norm(b-center),
                 np.linalg.norm((a+b)*.5-center))<.023
        count=max(1,math.ceil(np.linalg.norm(b-a)/maximum_step)) if near else 1
        result.extend(tuple(a+(b-a)*j/count) for j in range(count))
    return result


def chamfer_profile(x, width, ease_radius=.0003):
    """Height and derivative for a 45-degree ramp with tangent edge eases.

    Both overall horizontal spread and vertical rise equal width. The long
    central segment has slope exactly 1; small circular joins replace only its
    ends. Narrow eye protection scales radius down with local chamfer width.
    """
    radius=min(ease_radius,width*.25)
    x=max(0.0,min(width,x))
    outer_end=radius*(1-1/math.sqrt(2))
    inner_start=width-radius/math.sqrt(2)
    if x<=0:return 0.0,float('inf')
    if x<outer_end:
        height=math.sqrt(max(0.0,radius*radius-(radius-x)**2))
        return height,(radius-x)/max(height,1e-15)
    if x<=inner_start:return x+radius*(math.sqrt(2)-1),1.0
    dy=math.sqrt(max(0.0,radius*radius-(width-x)**2))
    return width-radius+dy,(width-x)/max(dy,1e-15)


def profile_stations(width, ease_radius=.0003):
    radius=min(ease_radius,width*.25)
    return [0.0,
            radius*(1-math.cos(math.pi/8))/width,
            radius*(1-1/math.sqrt(2))/width,
            1-radius/math.sqrt(2)/width,
            1-radius*math.cos(3*math.pi/8)/width,
            1.0]


def build():
    source_coords=smooth_polygon(OUTLINE)
    seat_indices=list(range(10*4,13*4+1))
    seat_delta=max(abs(source_coords[i][1]-1.6684) for i in seat_indices)
    for i in seat_indices:
        source_coords[i]=(source_coords[i][0],1.6684)
    outer = orient(Polygon(source_coords), sign=1)
    assert outer.is_valid and not outer.interiors
    eye = ref((604,287))
    width, eye_width, cap_depth = .0048, .0006, .0125
    eye_join_fillet=.0020
    eye_join_region=Point(eye).buffer(.027,quad_segs=32)
    outer_stations=profile_stations(width)
    hole_stations=profile_stations(eye_width)
    sections=len(outer_stations)-1
    outer_contours, hole_contours, hole_heights = [], [], []
    contour_reports = []
    for section,ease in enumerate(outer_stations):
        inset = width*ease
        if section == 0:
            poly = outer
        else:
            # Shrink the protected disk very slightly between sections. A
            # constant disk creates coincident XZ arcs at different depths,
            # which need vertical walls rather than annular triangulation.
            eye_protection = outer.intersection(Point(eye).buffer(.011 + eye_width*(1-ease), quad_segs=32))
            clip=outer.buffer(-eye_width*ease,quad_segs=12)
            poly = (outer.buffer(-inset, quad_segs=12)
                    .union(eye_protection)
                    .intersection(clip).buffer(0))
            # A raw union leaves36-53degree concave changes where the protected
            # disk meets the wide inset. A local morphological closing rolls
            # a2mm fillet through those joins. This operator is inclusion-
            # monotone, retaining nested strips; it only adds cap area, so the
            # pierced web is never reduced. The original outside clip stays.
            rounded=poly.buffer(eye_join_fillet,quad_segs=16).buffer(-eye_join_fillet,quad_segs=16)
            poly=(poly.union(rounded.intersection(eye_join_region))
                  .intersection(clip).buffer(0).simplify(1e-7,preserve_topology=True))
        assert poly.geom_type == 'Polygon' and poly.is_valid and not poly.interiors, (
            'Non-simple shoulder contour', section, poly.geom_type)
        coords = sample_eye_transition(clean_contour(poly),eye)
        poly = Polygon(coords)
        if outer_contours:
            previous = Polygon(outer_contours[-1])
            assert poly.difference(previous).area < 1e-13, ('Non-nested shoulder contour', section, poly.difference(previous).area)
            assert previous.boundary.distance(poly.boundary) > 1e-8, ('Touching shoulder contours', section)
        outer_contours.append(coords)
        hole_fraction=hole_stations[section]
        hole_contours.append(circle(eye,.008+eye_width*hole_fraction))
        hole_heights.append(cap_depth-eye_width+chamfer_profile(eye_width*hole_fraction,eye_width)[0])
        contour_reports.append({'section':section, 'nominal_inset_m':inset,
                                'outer_vertices':len(coords),
                                'nominal_half_depth_m':cap_depth-width+chamfer_profile(inset,width)[0]})
    cap_polygon = Polygon(outer_contours[-1], [hole_contours[-1]])
    assert cap_polygon.is_valid and not cap_polygon.is_empty, 'Eye bevel overlaps outside shoulder'
    web = Polygon(outer_contours[-1]).boundary.distance(Polygon(hole_contours[-1]).boundary)
    assert web > 0, 'No cap web remains at eye'
    cap_outer=Polygon(outer_contours[-1])
    local_concave_turns=[]
    for i,p in enumerate(outer_contours[-1]):
        if np.linalg.norm(np.asarray(p)-np.asarray(eye))>=.027:continue
        a=np.asarray(p)-np.asarray(outer_contours[-1][i-1])
        b=np.asarray(outer_contours[-1][(i+1)%len(outer_contours[-1])])-np.asarray(p)
        turn=math.degrees(math.atan2(a[0]*b[1]-a[1]*b[0],float(np.dot(a,b))))
        if turn<0:local_concave_turns.append(-turn)
    max_eye_join_turn=max(local_concave_turns,default=0.0)
    assert max_eye_join_turn<15.0, ('Sharp concave protected-eye cap join remains',max_eye_join_turn)

    vertices, vertex_normals, faces, groups = [], [], [], []
    projected_checks = []

    def add_loop(coords, side, section, is_hole=False):
        indices = list(range(len(vertices), len(vertices)+len(coords)))
        fraction=(hole_stations if is_hole else outer_stations)[section]
        local_widths=[];local_fractions=[];depths=[]
        for point in coords:
            if is_hole:
                local_width=eye_width
                local_fraction=fraction
            else:
                q=Point(point)
                foot=outer.boundary.interpolate(outer.boundary.project(q))
                # ONE boundary-anchored width field controls the rim AND all
                # subsequent inset strips. Independently recovering width per
                # strip can reverse the first slope beside the protected eye.
                local_width=min(width,cap_outer.boundary.distance(foot))
                local_fraction=min(1.0,outer.boundary.distance(q)/max(1e-8,local_width))
            local_width=max(1e-8,local_width)
            local_widths.append(local_width)
            local_fractions.append(local_fraction)
            value=cap_depth-local_width+chamfer_profile(local_width*local_fraction,local_width)[0]
            # Merge sub-micron residuals into the exact cap plane, rather than
            # retaining near-flat sliver slopes at the protected-eye fillet.
            if cap_depth-value<1e-6:value=cap_depth
            depths.append(value)
        for i, point in enumerate(coords):
            depth=depths[i]
            vertices.append((float(point[0]),float(side*depth),float(point[1])))
            if section == sections or abs(depth-cap_depth)<1e-10:
                # Exact flat-cap normal; shared cap/shoulder corners agree.
                normal = np.asarray((0.0, float(side), 0.0))
            else:
                if is_hole:
                    inward = np.asarray(eye)-np.asarray(point)
                    outward = inward/np.linalg.norm(inward)
                else:
                    # Equal-weight unit tangents avoid bias from the unequal
                    # vertex spacing introduced by polygon offset joins.
                    p = np.asarray(point)
                    incoming = p-np.asarray(coords[i-1])
                    outgoing = np.asarray(coords[(i+1)%len(coords)])-p
                    tangent = incoming/np.linalg.norm(incoming) + outgoing/np.linalg.norm(outgoing)
                    tangent /= np.linalg.norm(tangent)
                    outward = np.asarray((tangent[1],-tangent[0]))
                if section == 0:
                    normal = np.asarray((outward[0],0.0,outward[1]))
                elif is_hole:
                    slope=chamfer_profile(eye_width*hole_stations[section],eye_width)[1]
                    normal=np.asarray((outward[0]*slope,float(side),outward[1]*slope))
                    normal/=np.linalg.norm(normal)
                else:
                    slope=chamfer_profile(local_widths[i]*local_fractions[i],local_widths[i])[1]
                    # Tangential correction follows the tapered rim height at
                    # the eye instead of forcing a steep full-depth pinch.
                    span=np.linalg.norm(np.asarray(coords[(i+1)%len(coords)])-np.asarray(coords[i-1]))
                    along=(depths[(i+1)%len(coords)]-depths[i-1])/max(span,1e-12)
                    lateral=outward*slope-tangent*along
                    normal=np.asarray((lateral[0],float(side),lateral[1]))
                    normal/=np.linalg.norm(normal)
            vertex_normals.append(tuple(map(float,normal)))
        return indices

    def annulus(outer_coords, outer_ids, inner_coords, inner_ids, group):
        coords = np.asarray(outer_coords+inner_coords, dtype=np.float64)
        ends = np.asarray([len(outer_coords), len(coords)], dtype=np.uint32)
        polygon = Polygon(outer_coords, [inner_coords])
        assert polygon.is_valid and polygon.area > 0, ('Invalid annulus', group)
        # Constrained Delaunay also retains the locally inserted collinear
        # boundary samples, unlike cap triangulators that omit those vertices.
        # Keep all shared boundary vertices to avoid T-junctions between strips.
        lookup={tuple(p):i for i,p in enumerate(coords)}
        result=np.asarray([[lookup[tuple(p)] for p in list(t.exterior.coords)[:3]]
                           for t in constrained_delaunay_triangles(polygon).geoms],dtype=np.uint32)
        ids = outer_ids+inner_ids
        total_area = 0.0
        for tri in result:
            a,b,c = coords[tri]
            cross = (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
            assert abs(cross) > 1e-16, ('Degenerate projected triangle', group)
            triangle = Polygon((a,b,c))
            assert triangle.difference(polygon).area < 1e-13, ('Triangle crosses annulus', group)
            total_area += abs(cross)*.5
            faces.append([ids[int(i)] for i in tri])
            groups.append(group)
        assert abs(total_area-polygon.area) < max(1e-13, polygon.area*1e-8), ('Coverage mismatch', group)
        # Each specified loop vertex must participate, otherwise earcut removed
        # a redundant point and would leave a T-junction against the next strip.
        assert set(map(int,result.ravel())) == set(range(len(coords))), ('Unused boundary vertex', group)
        projected_checks.append({'group':group, 'triangles':len(result), 'area_m2':polygon.area})

    outer_ids, hole_ids = {}, {}
    for side in (-1,1):
        outer_ids[side] = [add_loop(p,side,k) for k,p in enumerate(outer_contours)]
        hole_ids[side] = [add_loop(p,side,k,True) for k,p in enumerate(hole_contours)]
        for k in range(sections):
            annulus(outer_contours[k],outer_ids[side][k],
                    outer_contours[k+1],outer_ids[side][k+1],f'outer_chamfer_{side}_{k}')
            # Increasing hole radius: the higher cap-facing loop is exterior.
            annulus(hole_contours[k+1],hole_ids[side][k+1],
                    hole_contours[k],hole_ids[side][k],f'eye_chamfer_{side}_{k}')
        annulus(outer_contours[-1],outer_ids[side][-1],
                hole_contours[-1],hole_ids[side][-1],f'flat_cap_{side}')

    for label, loops in [('outer_wall',outer_ids),('eye_wall',hole_ids)]:
        a,b = loops[-1][0],loops[1][0]
        assert len(a)==len(b)
        for j in range(len(a)):
            nxt=(j+1)%len(a)
            faces.extend(([a[j],a[nxt],b[nxt]],[a[j],b[nxt],b[j]]))
            groups.extend((label,label))

    # Orient the entire closed surface consistently without assuming earcut's
    # orientation in the XZ-to-XYZ mapping.
    edges = defaultdict(list)
    for fi, face in enumerate(faces):
        for a,b in zip(face,face[1:]+face[:1]):
            edges[tuple(sorted((a,b)))].append((fi, a<b))
    bad = [(edge,links) for edge,links in edges.items() if len(links)!=2]
    assert not bad, ('Non-manifold edges',bad[:5])
    flags={0:False}; queue=deque([0])
    while queue:
        fi=queue.popleft(); face=faces[fi]
        for a,b in zip(face,face[1:]+face[:1]):
            links=edges[tuple(sorted((a,b)))]
            other=links[1] if links[0][0]==fi else links[0]
            required=flags[fi] ^ ((a<b)==other[1])
            if other[0] in flags:
                assert flags[other[0]]==required, 'Non-orientable surface'
            else:
                flags[other[0]]=required;queue.append(other[0])
    assert len(flags)==len(faces), 'Disconnected casting surface'
    for fi,reverse in flags.items():
        if reverse:faces[fi].reverse()
    array=np.asarray(vertices,dtype=np.float64)
    assert np.isfinite(array).all()
    normal_array=np.asarray(vertex_normals,dtype=np.float64)
    assert np.isfinite(normal_array).all()
    assert np.max(np.abs(np.linalg.norm(normal_array,axis=1)-1))<1e-10
    volume=sum(float(np.dot(array[f[0]],np.cross(array[f[1]],array[f[2]]))) for f in faces)/6
    if volume<0:
        faces=[list(reversed(f)) for f in faces];volume=-volume
    assert volume>1e-8
    assert len(vertices)-len(edges)+len(faces)==0, 'Pierced closed solid should have Euler characteristic zero'
    for f,group in zip(faces,groups):
        area=np.linalg.norm(np.cross(array[f[1]]-array[f[0]],array[f[2]]-array[f[0]]))*.5
        assert area>1e-13, ('Degenerate spatial triangle',float(area),group,f)
    corner_normals=[]
    for face,group in zip(faces,groups):
        if group.startswith('flat_cap_'):
            side=-1.0 if array[face[0],1]<0 else 1.0
            values=[(0.0,side,0.0)]*3
        elif group in ('outer_wall','eye_wall'):
            # Wall corners remain horizontal even when the eye protection
            # changes the rim depth. Do not inherit a chamfer/cap average.
            values=[]
            geometric=np.cross(array[face[1]]-array[face[0]],array[face[2]]-array[face[0]])
            geometric/=np.linalg.norm(geometric)
            for i in face:
                normal=np.asarray(vertex_normals[i]);normal[1]=0;normal/=np.linalg.norm(normal)
                # Split genuinely sharp outline tips from the adjoining wall.
                if float(np.dot(normal,geometric))<math.cos(math.radians(35)):
                    normal=geometric
                values.append(tuple(map(float,normal)))
        else:
            values=[vertex_normals[i] for i in face]
        corner_normals.append(values)
    corner_array=np.asarray(corner_normals)
    assert np.isfinite(corner_array).all()
    assert np.max(abs(np.linalg.norm(corner_array,axis=2)-1))<1e-10
    assert all(chamfer_profile(width*q,width)[1]==1.0 for q in (.1,.25,.5,.75,.9))
    triangles=np.asarray(faces,dtype=np.int64)
    cross=np.cross(array[triangles[:,1]]-array[triangles[:,0]],array[triangles[:,2]]-array[triangles[:,0]])
    areas=np.linalg.norm(cross,axis=1)*.5
    geom_normals=cross/(areas*2)[:,None]
    # Very narrow explicit ease triangles near the eye can turn away from
    # their analytic contour normal. Corner normals must respect the ACTUAL
    # oriented triangle, not merely the nominal profile. Preserve geometry;
    # use the face normal for backward/ambiguous corners and constrain other
    # grazing normals to a60-degree cone around the oriented face normal.
    corner_array=np.asarray(corner_normals,dtype=np.float64)
    dots_before=np.sum(corner_array*geom_normals[:,None,:],axis=2)
    corrections=np.argwhere(dots_before<.5)
    corrected_groups=defaultdict(int)
    for face_index,corner_index in corrections:
        geometric=geom_normals[face_index]
        normal=corner_array[face_index,corner_index]
        dot=float(dots_before[face_index,corner_index])
        tangent=normal-geometric*dot
        length=float(np.linalg.norm(tangent))
        if dot<=.05 or length<1e-10:
            fixed=geometric
        else:
            fixed=.5*geometric+math.sqrt(.75)*tangent/length
        corner_array[face_index,corner_index]=fixed/np.linalg.norm(fixed)
        corrected_groups[groups[face_index]]+=1
    dots_after=np.sum(corner_array*geom_normals[:,None,:],axis=2)
    assert np.isfinite(corner_array).all()
    assert np.max(abs(np.linalg.norm(corner_array,axis=2)-1))<1e-10
    assert float(dots_after.min())>=.5-1e-10
    corner_normals=corner_array.tolist()
    main=np.asarray([g.startswith('outer_chamfer') and g.endswith('_2') for g in groups])
    angles=np.degrees(np.arccos(np.minimum(1,np.abs(geom_normals[main,1]))))
    main_areas=areas[main]
    near_45=float(main_areas[(angles>=40)&(angles<=50)].sum()/main_areas.sum())
    assert near_45>.90, ('Main chamfer triangulation inclines incorrectly',near_45)
    ramp_dots=[]
    for face_index,group in enumerate(groups):
        if not group.startswith('outer_chamfer'):continue
        center=array[triangles[face_index]].mean(axis=0)
        q=Point(center[0],center[2])
        foot=outer.boundary.interpolate(outer.boundary.project(q))
        outward=np.asarray((foot.x-center[0],foot.y-center[2]))
        outward/=np.linalg.norm(outward)
        ramp_dots.append(float(np.dot(geom_normals[face_index,[0,2]],outward)))
    reversed_ramps=sum(value<-1e-8 for value in ramp_dots)
    assert reversed_ramps==0, ('Geometrically reversed outer chamfer slopes',reversed_ramps,min(ramp_dots))
    report={
        'construction':'Explicit wide45-degree chamfer with small tangent edge eases; nested triangulated strips',
        'outer_nominal_bevel_mm':width*1000,'eye_bevel_mm':eye_width*1000,
        'outer_nominal_depth_mm':width*1000,'central_slope_degrees':45.0,
        'edge_ease_radius_mm':.3,
        'outer_wall_half_depth_m':cap_depth-width, 'cap_half_depth_m':cap_depth,
        'eye_protection':'Local horizontal spread and vertical drop taper together; no full-depth narrow eye bevel',
        'eye_protection_join_fillet_mm':eye_join_fillet*1000,
        'eye_cap_maximum_concave_turn_degrees':max_eye_join_turn,
        'eye_transition_sampling_max_step_mm':.5,
        'cap_plane_residual_snap_microns':1.0,
        'protected_width_field':'One width anchored at the original outer-boundary footpoint for every inset; no independently changing rim/strip depth',
        'sections':sections,'eye_cap_web_mm':web*1000,
        'vertices':len(vertices),'triangles':len(faces),'manifold_edges':True,
        'consistent_winding':True,'finite':True,'positive_volume_m3':volume,
        'euler_characteristic':0,'contours':contour_reports,
        'projected_triangle_coverage_checked':True,
        'projected_strips_disjoint_by_nested_boundaries':True,
        'shoulder_triangulation':'Constrained Delaunay; avoids steep earcut diagonal fans',
        'main_chamfer_geometric_area_weighted_angle_deg':float(np.average(angles,weights=main_areas)),
        'main_chamfer_geometric_area_fraction_40_to_50deg':near_45,
        'geometric_ramp_direction_audit':{
            'outer_triangle_count':len(ramp_dots),
            'minimum_outward_projected_normal_dot':min(ramp_dots),
            'reversed_outer_slopes':reversed_ramps,
            'reversal_tolerance_dot':-1e-8},
        'inclination_scope':'Straight shoulder areas approach45deg; converging corner and protected-eye patches vary',
        'original_outer_trace_preserved_except_socket_seat':True,
        'socket_seat':{'reference_point_indices':[10,11,12,13],'z_m':1.6684,
                       'maximum_z_correction_mm':seat_delta*1000,'x_preserved':True,
                       'other_original_outline_samples_unchanged':True},
        'vertex_normals':'Depth-field normals for explicit chamfer; cap exactly +/-Y',
        'corner_normals':'Face-aligned3 normals per triangle; flat cap/wall corners classified independently',
        'corner_normal_geometry_audit':{
            'minimum_dot_before':float(dots_before.min()),
            'backward_corners_before':int((dots_before<0).sum()),
            'corrected_corner_count':int(len(corrections)),
            'corrected_groups':dict(corrected_groups),
            'minimum_dot_after':float(dots_after.min()),
            'backward_corners_after':int((dots_after<0).sum()),
            'all_finite_unit_normals':True,
            'geometry_unchanged_by_normal_correction':True},
        'shading_guidance':'Use corner_normals[face_index][corner_index] in original face order; no automatic averaging or weighted-normal modifier.',
    }
    return {'vertices':vertices,'vertex_normals':vertex_normals,'corner_normals':corner_normals,
            'faces':faces,'face_regions':groups,'report':report}


if __name__=='__main__':
    payload=build()
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(payload,separators=(',',':')),encoding='utf-8')
    print(json.dumps({'output':str(OUTPUT),**payload['report']},indent=2))
