"""Read-only Blender audit of selected lotus pommel, after export_spear.py.

Run through the existing Blender MCP session. No scene, mesh, material, camera,
or file-save operation is performed; only the JSON verification record is written.
"""
import bpy
import bmesh
import hashlib
import json
import math
import runpy
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy')
WORK = ROOT/'Saved/Diagnostics/ImperialSpear/PommelLotus'
BASELINE = ROOT/'Saved/Diagnostics/ImperialSpear/PommelLeaf'
OUT = ROOT/'Exports/ImperialSpear'
GRIP = 1.235
PREFIXES = ('02 •', 'Pommel •')
REPORT_PATH = OUT/'Pommel_Lotus_Verification.json'
report = {'status': 'AUDIT_IN_PROGRESS', 'concept': '04 — Lotus bud',
          'unreal_import_cooking_and_physics_validated': False}


def fingerprint(o):
    # Deliberately identical to the saved pre-pommel source baseline.
    m=o.data
    d={'v':[list(v.co) for v in m.vertices],'f':[list(p.vertices) for p in m.polygons],
       'uv':{l.name:[list(v.uv) for v in l.data] for l in m.uv_layers},
       'normals':[list(n.vector) for n in m.corner_normals],
       'materials':[sl.material.name if sl.material else None for sl in o.material_slots],
       'matrix':[list(r) for r in o.matrix_world]}
    return hashlib.sha256(json.dumps(d,separators=(',',':')).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def world_points(ob):
    return [ob.matrix_world@v.co for v in ob.data.vertices]


def point_bounds(points):
    return {'min': [min(p[i] for p in points) for i in range(3)],
            'max': [max(p[i] for p in points) for i in range(3)]}


def triangles(ob):
    return sum(len(p.vertices)-2 for p in ob.data.polygons)


def mesh_audit(ob, convex=False):
    """Inspect world-space copies, retaining every authored normal and face."""
    points = world_points(ob)
    require(points and all(math.isfinite(c) for p in points for c in p),
            f'{ob.name}: empty or nonfinite mesh')
    require(not any(mod.show_render for mod in ob.modifiers),
            f'{ob.name}: unapplied render modifier')
    bm = bmesh.new()
    try:
        bm.from_mesh(ob.data)
        bm.transform(ob.matrix_world)
        bm.normal_update()
        row = {'vertices': len(bm.verts), 'triangles': triangles(ob),
               'nonmanifold_edges': sum(not e.is_manifold for e in bm.edges),
               'inconsistent_winding_edges': sum(not e.is_contiguous for e in bm.edges),
               'loose_vertices': sum(not v.link_faces for v in bm.verts),
               'volume_m3': bm.calc_volume(signed=True),
               'minimum_face_area_m2': min(f.calc_area() for f in bm.faces),
               'minimum_edge_length_m': min(e.calc_length() for e in bm.edges),
               'bounds_m': point_bounds(points)}
        planes = [(tuple(f.normal), float(f.normal.dot(f.verts[0].co))) for f in bm.faces]
        require(row['nonmanifold_edges'] == row['inconsistent_winding_edges'] == row['loose_vertices'] == 0,
                f'{ob.name}: mesh is not a closed, consistently oriented surface: {row}')
        require(row['volume_m3'] > 0 and row['minimum_face_area_m2'] > 1e-14
                and row['minimum_edge_length_m'] > 1e-9,
                f'{ob.name}: nonpositive volume or degenerate surface: {row}')
        if convex:
            violation = max(p.dot(Vector(n))-h for n, h in planes for p in points)
            row['convex_max_plane_violation_m'] = violation
            require(4 <= row['vertices'] <= 64 and violation < 1e-6,
                    f'{ob.name}: invalid simple convex hull: {row}')
    finally:
        bm.free()
    ob.data.calc_loop_triangles()
    areas = [((points[t.vertices[1]]-points[t.vertices[0]]).cross(
               points[t.vertices[2]]-points[t.vertices[0]])).length*.5
             for t in ob.data.loop_triangles]
    row['minimum_triangle_area_m2'] = min(areas)
    require(len(areas) == row['triangles'] and min(areas) > 1e-14,
            f'{ob.name}: source tessellation contains a degenerate triangle')
    return row, planes


_BVH_TRIANGLES = {}
_WINDING_STATS = {}


def reset_winding_stats():
    _WINDING_STATS.clear()
    _WINDING_STATS.update(checks=0, disagreement_checks=0, negative_parity_checks=0,
                          corrected_false_negatives=0, corrected_false_positives=0,
                          stalled_parity_rays=0, stalled_parity_queries=0,
                          confirmed_outside=0, maximum_integer_residual=0., examples=[])


reset_winding_stats()


def source_bvh(ob):
    ob.data.calc_loop_triangles()
    points = world_points(ob)
    faces = [tuple(t.vertices) for t in ob.data.loop_triangles]
    tree = BVHTree.FromPolygons(points, faces, all_triangles=True, epsilon=1e-9)
    # Cache the actual tessellated surface in Python doubles. Winding arithmetic
    # below never uses mathutils.Vector operations (which may use float32).
    positions = [tuple(float(c) for c in p) for p in points]
    _BVH_TRIANGLES[id(tree)] = tuple(tuple(positions[i] for i in face) for face in faces)
    return tree


def solid_angle_winding(triangles, point):
    """Generalized winding number from oriented triangle solid angles.

    A consistently oriented closed shell gives magnitude1 inside and0 outside.
    math.fsum and scalar Python float arithmetic avoid ray-edge, grazing-face,
    and single-precision self-reintersection ambiguity. The geometry and query
    are not inflated, moved or otherwise given a looser containment tolerance.
    """
    px, py, pz = (float(c) for c in point)
    angles = []
    for first, second, third in triangles:
        ax, ay, az = first[0]-px, first[1]-py, first[2]-pz
        bx, by, bz = second[0]-px, second[1]-py, second[2]-pz
        cx, cy, cz = third[0]-px, third[1]-py, third[2]-pz
        la = math.sqrt(ax*ax+ay*ay+az*az)
        lb = math.sqrt(bx*bx+by*by+bz*bz)
        lc = math.sqrt(cx*cx+cy*cy+cz*cz)
        require(min(la, lb, lc)>1e-15, 'Winding query lies on a triangle vertex; boundary classification failed')
        numerator = ax*(by*cz-bz*cy)+ay*(bz*cx-bx*cz)+az*(bx*cy-by*cx)
        denominator = (la*lb*lc+(ax*bx+ay*by+az*bz)*lc
                       +(bx*cx+by*cy+bz*cz)*la+(cx*ax+cy*ay+cz*az)*lb)
        angles.append(2.*math.atan2(numerator, denominator))
    winding = math.fsum(angles)/(4.*math.pi)
    require(math.isfinite(winding), 'Nonfinite generalized winding number')
    magnitude = abs(winding)
    residual = min(magnitude, abs(magnitude-1.))
    require(residual < 1e-5,
            f'Closed-surface winding is ambiguous/noninteger: winding={winding}, point={tuple(point)}')
    return winding, magnitude>.5, residual


RAY_DIRECTIONS = [Vector(v).normalized() for v in
                  ((.937, .271, .221), (-.317, .889, .329), (.271, -.417, .867))]


def contains_point(tree, point, boundary_tolerance_m=2e-6):
    """BVH parity with independent solid-angle checks for ambiguous/negative votes."""
    nearest = tree.find_nearest(point)
    if nearest[0] is not None and nearest[3] <= boundary_tolerance_m:
        return True, float(nearest[3]), True
    votes = []
    stalled_rays = []
    for ray_index, direction in enumerate(RAY_DIRECTIONS):
        origin = point.copy()
        crossings = 0
        for _ in range(64):
            hit, _normal, _index, _distance = tree.ray_cast(origin, direction, 1.)
            if hit is None:
                break
            crossings += 1
            origin = hit+direction*2e-7
        else:
            # A float32 BVH ray can repeatedly re-hit a thin face despite the
            # origin nudge. Its parity is indeterminate, not geometric evidence
            # that the closed shell is invalid. Classify with winding below.
            stalled_rays.append(ray_index)
            votes.append(None)
            continue
        votes.append(bool(crossings % 2))
    parity_inside = (sum(votes) >= 2) if not stalled_rays else None
    unanimous = not stalled_rays and len(set(votes)) == 1
    distance = float(nearest[3]) if nearest[0] is not None else math.inf
    if stalled_rays or not unanimous or parity_inside is False:
        require(id(tree) in _BVH_TRIANGLES, 'Winding fallback requires the actual source tessellation')
        winding, inside, residual = solid_angle_winding(_BVH_TRIANGLES[id(tree)], point)
        _WINDING_STATS['checks'] += 1
        _WINDING_STATS['disagreement_checks'] += int(not unanimous)
        _WINDING_STATS['negative_parity_checks'] += int(parity_inside is False)
        _WINDING_STATS['corrected_false_negatives'] += int(inside and parity_inside is False)
        _WINDING_STATS['corrected_false_positives'] += int(not inside and parity_inside is True)
        _WINDING_STATS['stalled_parity_rays'] += len(stalled_rays)
        _WINDING_STATS['stalled_parity_queries'] += int(bool(stalled_rays))
        _WINDING_STATS['confirmed_outside'] += int(not inside)
        _WINDING_STATS['maximum_integer_residual'] = max(_WINDING_STATS['maximum_integer_residual'], residual)
        if len(_WINDING_STATS['examples'])<20:
            _WINDING_STATS['examples'].append({'position_m':[float(c) for c in point],
                'parity_votes':votes, 'parity_inside':parity_inside, 'winding_number':winding,
                'stalled_ray_indices':stalled_rays,
                'winding_inside':inside, 'nearest_surface_distance_m':distance})
        return inside, distance, unanimous
    return parity_inside, distance, unanimous


def wood_joint_audit(shaft, pommel):
    """Sample the actual faceted shaft surface inside the final gold fitting.

    Z sections are at most 1mm apart and include all source-ring levels and
    inter-level midpoints. Actual shaft-face boundary segments are sampled at
    most 0.5mm apart. This is a dense sampled surface check, not a proof over
    every point of a continuous union. No idealized circular shaft is used.
    """
    reset_winding_stats()
    points = world_points(shaft)
    top = max(p.z for ob in pommel for p in world_points(ob))
    low = min(p.z for p in points)
    require(.11 < top < .16 and low < top,
            f'Unexpected wood/pommel joint bounds: {low}..{top}')
    n = max(1, math.ceil((top-low)/.001))
    levels = {low+(top-low)*i/n for i in range(n+1)}
    levels.update(p.z for ob in pommel for p in world_points(ob) if low <= p.z <= top)
    levels.update(p.z for p in points if low <= p.z <= top)
    ordered = sorted(levels)
    levels.update((a+b)*.5 for a, b in zip(ordered, ordered[1:]))
    samples = {}
    for z in sorted(levels):
        for face in shaft.data.polygons:
            vs = [points[i] for i in face.vertices]
            if max(p.z for p in vs)-min(p.z for p in vs) < 1e-8:
                continue  # Side-boundary sections cover the perimeter of the buried end cap.
            cuts = []
            for a, b in zip(vs, vs[1:]+vs[:1]):
                if abs(a.z-z) < 1e-9:
                    cuts.append(a.copy())
                if (a.z-z)*(b.z-z) < 0:
                    cuts.append(a.lerp(b, (z-a.z)/(b.z-a.z)))
            if len(cuts) < 2:
                continue
            a, b = max(((a, b) for i, a in enumerate(cuts) for b in cuts[i+1:]),
                       key=lambda pair: (pair[1]-pair[0]).length_squared)
            steps = max(1, math.ceil((b-a).length/.0005))
            for i in range(steps+1):
                p = a.lerp(b, i/steps)
                samples[tuple(round(c, 9) for c in p)] = p
    require(samples, 'No actual wood-surface joint samples were produced')
    trees = [(ob.name, source_bvh(ob), point_bounds(world_points(ob))) for ob in pommel]
    outside, vote_disagreements = [], 0
    owner_counts = {name: 0 for name, _tree, _bounds in trees}
    minimum_accepted_nearest_m = math.inf
    for point in samples.values():
        accepted = False
        best_distance = math.inf
        for name, tree, box in trees:
            if any(point[i] < box['min'][i]-2e-6 or point[i] > box['max'][i]+2e-6 for i in range(3)):
                continue
            inside, distance, unanimous = contains_point(tree, point)
            if not unanimous:
                vote_disagreements += 1
            best_distance = min(best_distance, distance)
            if inside:
                accepted = True
                owner_counts[name] += 1
                minimum_accepted_nearest_m = min(minimum_accepted_nearest_m, distance)
                break
        if not accepted:
            outside.append({'position_m': list(point), 'nearest_checked_pommel_distance_m':
                            best_distance if math.isfinite(best_distance) else None})
    result = {'status': 'PASS' if not outside else 'FAIL',
              'method': 'actual shaft face sections; BVH parity with double-precision closed-surface solid-angle winding for stalled, ambiguous or negative votes',
              'continuous_surface_proof': False, 'source_z_span_m': [low, top],
              'axial_sections': len(levels), 'maximum_axial_step_m': .001,
              'maximum_cross_section_step_m': .0005, 'boundary_tolerance_m': 2e-6,
              'samples': len(samples), 'outside_samples': len(outside),
              'ray_vote_disagreements': vote_disagreements,
              'winding_fallback': dict(_WINDING_STATS),
              'containing_component_sample_counts': owner_counts,
              'minimum_accepted_nearest_surface_distance_m':
                  minimum_accepted_nearest_m if math.isfinite(minimum_accepted_nearest_m) else None,
              'outside_examples': outside[:20]}
    report['wood_joint'] = result
    require(not outside, f'Wood protrudes from pommel at {len(outside)} sampled surface points: {outside[:3]}')
    return result


def main():
    art = bpy.data.collections['SPEAR • editable components']
    game = bpy.data.scenes['GAME • Unreal export']
    objects = {ob.name: ob for ob in art.objects if ob.type == 'MESH'}
    baseline = json.loads((BASELINE/'Baseline_Source_Components.json').read_text(encoding='utf-8'))
    protected = {name: row for name, row in baseline.items() if not name.startswith(PREFIXES)}
    require(len(protected) == 70, f'Expected 70 protected components, found {len(protected)}')
    pommel_names={name for name in objects if name.startswith(PREFIXES)}
    require('02 • carved lotus pommel body' in pommel_names and len(pommel_names)>=3,
            f'Missing rebuilt lotus components: {sorted(pommel_names)}')
    require(set(objects) == set(protected)|pommel_names,
            f'Source object set mismatch: added={sorted(set(objects)-set(protected)-pommel_names)}, '
            f'missing={sorted(set(protected)-set(objects))}')
    checked = {}
    for name, row in protected.items():
        actual = fingerprint(objects[name])
        require(actual == row['fingerprint'], f'Protected component changed: {name}')
        checked[name] = actual
    report['protected_component_count'] = len(checked)
    report['protected_full_source_fingerprints'] = checked

    expected_textures = json.loads((BASELINE/'Protected_Texture_Hashes.json').read_text(encoding='utf-8'))
    actual_texture_paths = {p.name: p for p in (OUT/'Textures').glob('T_ImperialSpear_*.png')}
    require(set(actual_texture_paths) == set(expected_textures), 'Protected atlas file set changed')
    actual_hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in actual_texture_paths.items()}
    require(actual_hashes == expected_textures, f'Protected atlas bytes changed: '
            f'{[name for name in expected_textures if actual_hashes[name] != expected_textures[name]]}')
    report['all_atlas_file_hashes_unchanged'] = actual_hashes

    pommel = [objects[name] for name in sorted(pommel_names)]
    report['pommel_components'] = {}
    for ob in pommel:
        row, _planes = mesh_audit(ob)
        require(ob.get('PommelDesign') == 'lotus_bud', f'Missing design marker: {ob.name}')
        require(len(ob.data.materials)==1 and ob.data.materials[0].name=='M_ImperialSpear_PBR',
                f'Pommel must use the accepted shared gold material: {ob.name}')
        require(len(ob.data.uv_layers) == 1 and ob.data.uv_layers[0].name == 'UV0_SurfaceAtlas',
                f'Unexpected source UV layout: {ob.name}')
        require(len(ob.data.corner_normals) == len(ob.data.loops) and
                all(c.vector.length > .5 and all(math.isfinite(v) for v in c.vector) for c in ob.data.corner_normals),
                f'Invalid source custom normals: {ob.name}')
        require(all(math.isfinite(v) for item in ob.data.uv_layers[0].data for v in item.uv),
                f'Nonfinite source UV: {ob.name}')
        uv = ob.data.uv_layers[0].data
        row['uv_bounds']={'min':[min(item.uv[i] for item in uv) for i in range(2)],
                          'max':[max(item.uv[i] for item in uv) for i in range(2)]}
        require(all(.5015-1e-6<=item.uv.x<=.7485+1e-6 and .7515-1e-6<=item.uv.y<=.9985+1e-6 for item in uv),
                f'Pommel UV extends beyond the accepted plain-gold tile: {ob.name}: {row["uv_bounds"]}')
        uv_areas = []
        normal_dots = []
        for triangle in ob.data.loop_triangles:
            ta,tb,tc = [uv[i].uv for i in triangle.loops]
            ab,ac = tb-ta,tc-ta
            uv_areas.append(abs(ab.x*ac.y-ab.y*ac.x)*.5)
            for i in triangle.loops:
                normal_dots.append(ob.data.corner_normals[i].vector.dot(triangle.normal))
        row['minimum_triangle_uv_area'] = min(uv_areas)
        row['minimum_custom_normal_geometric_normal_dot'] = min(normal_dots)
        require(min(uv_areas)>1e-12, f'Collapsed UV triangle: {ob.name}')
        require(min(normal_dots)>0, f'Inward shading normal: {ob.name}')
        row['fingerprint'] = fingerprint(ob)
        report['pommel_components'][ob.name] = row

    hulls = [ob for ob in game.objects if ob.type == 'MESH' and ob.name.startswith('UCX_SM_ImperialSpear_')]
    require(len(hulls) == 17, f'Expected 17 GAME convex hulls, found {len(hulls)}')
    roles = {}
    report['collision_hulls'] = {}
    for ob in hulls:
        row, planes = mesh_audit(ob, convex=True)
        role = ob.get('CollisionRole')
        require(role and role not in roles, f'Missing or duplicate collision role: {ob.name}: {role}')
        roles[role] = (ob, planes)
        report['collision_hulls'][ob.name] = {'role': role, **row}
    report['collision_hull_count'] = len(hulls)
    report['maximum_hull_vertices'] = max(len(ob.data.vertices) for ob in hulls)

    helper = runpy.run_path(str(ROOT/'Tools/SpearAsset/reference_collision_specs.py'))
    specs = helper['flattened_pommel_specs'](list(objects.values()), GRIP)
    require(specs is not None and len(specs) == 3, 'Lotus collision helper did not resolve three sections')
    report['actual_ucx_pommel_containment'] = {}
    for spec in specs:
        role = spec['role']
        require(role in roles, f'Missing actual pommel hull: {role}')
        ob, actual_planes = roles[role]
        points = helper['pommel_slab_points'](pommel, *spec['source_z_slab_m'])
        relative = [(x, y, z-GRIP) for x, y, z in points]
        containment = helper['envelope_containment_report'](relative, actual_planes, tolerance_m=1e-6)
        row = {'actual_ucx': ob.name, 'source_z_slab_m': spec['source_z_slab_m'],
               'actual_ucx_face_plane_count': len(actual_planes), **containment}
        report['actual_ucx_pommel_containment'][role] = row
        require(containment['source_contained'], f'Actual UCX cuts through source pommel: {role}: {row}')

    render = game.objects.get('SM_ImperialSpear')
    require(render is not None and render.type == 'MESH', 'Missing exported GAME render mesh')
    source_triangles = sum(triangles(ob) for ob in objects.values())
    source_vertices = sum(len(ob.data.vertices) for ob in objects.values())
    game_triangles = triangles(render)
    require(all(len(p.vertices) == 3 for p in render.data.polygons), 'GAME render mesh is not fully triangulated')
    require(game_triangles == source_triangles, f'Source/GAME triangles differ: {source_triangles}/{game_triangles}')
    require(len(render.data.vertices) == source_vertices, 'Source/GAME vertex counts differ')
    source_bounds = point_bounds([p for ob in objects.values() for p in world_points(ob)])
    game_bounds = point_bounds(world_points(render))
    bounds_error = max(abs(source_bounds[edge][i]-(GRIP if i == 2 else 0)-game_bounds[edge][i])
                       for edge in ('min', 'max') for i in range(3))
    source_bottom=source_bounds['min'][2]
    overall_length=source_bounds['max'][2]-source_bottom
    require(bounds_error < 2e-6 and -.060 < source_bottom < 0
            and abs(source_bounds['max'][2]-2.2) < 1e-6, 'Unexpected source/GAME length, pivot or bounds')
    require(abs(float(render.get('Length_m',0))-overall_length)<2e-6,'Stale overall-length metadata')
    require(abs(game.objects['SOCKET_SM_ImperialSpear_Pommel'].location.z-(source_bottom-GRIP))<2e-6,
            'Pommel socket is not at the actual bud tip')
    expected_materials={'M_ImperialSpear_PBR'}
    require({m.name for m in render.data.materials}==expected_materials,'GAME material slots changed')
    material_counts={m.name:0 for m in render.data.materials}
    for poly in render.data.polygons:material_counts[render.data.materials[poly.material_index].name]+=len(poly.vertices)-2
    require(material_counts['M_ImperialSpear_PBR']==source_triangles,
            'GAME shared material does not cover all source triangles')
    report['source_game_comparison'] = {'source_objects': len(objects),
        'source_triangles': source_triangles, 'game_triangles': game_triangles,
        'source_vertices': source_vertices, 'game_vertices': len(render.data.vertices),
        'pommel_triangles': sum(triangles(ob) for ob in pommel),
        'protected_triangles': sum(baseline[name]['triangles'] for name in protected),
        'source_bounds_m': source_bounds, 'game_bounds_grip_relative_m': game_bounds,
        'maximum_bounds_error_m': bounds_error, 'overall_length_m': overall_length,
        'source_bottom_z_m':source_bottom,'grip_reference_source_z_m':GRIP,
        'grip_from_pommel_m':GRIP-source_bottom,'material_triangles':material_counts}
    report['pommel_material']='M_ImperialSpear_PBR'
    report['pommel_uses_existing_plain_gold_atlas']=True
    shafts = [ob for ob in objects.values() if ob.name.startswith('01 •')]
    require(len(shafts) == 1, f'Expected one protected wood shaft, found {len(shafts)}')
    wood_joint_audit(shafts[0], pommel)
    report['status'] = 'LOTUS_POMMEL_SOURCE_AND_ACTUAL_GAME_COLLISION_AUDITED'


try:
    main()
except Exception as exc:
    report['status'] = 'FAILED'
    report['error'] = f'{type(exc).__name__}: {exc}'
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding='utf-8')
    raise
else:
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items()
                      if key not in ('protected_full_source_fingerprints', 'collision_hulls')}, indent=2))
