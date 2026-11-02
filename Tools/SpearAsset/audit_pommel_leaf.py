"""Read-only Blender audit of selected leaf pommel, after export_spear.py.

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
WORK = ROOT/'Saved/Diagnostics/ImperialSpear/PommelLeaf'
OUT = ROOT/'Exports/ImperialSpear'
GRIP = 1.235
PREFIXES = ('02 •', 'Pommel •')
EXPECTED_COMPONENTS = {
    '02 • flattened leaf pommel',
    'Pommel • turned socket with rolled lips',
    'Pommel • blunt rolled end cap',
}
REPORT_PATH = OUT/'Pommel_Leaf_Verification.json'
report = {'status': 'AUDIT_IN_PROGRESS', 'concept': '03 — Flattened leaf',
          'unreal_import_cooking_and_physics_validated': False}


def fingerprint(o):
    # Deliberately identical to model_pommel_leaf.py and the saved baseline.
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


def source_bvh(ob):
    ob.data.calc_loop_triangles()
    points = world_points(ob)
    faces = [tuple(t.vertices) for t in ob.data.loop_triangles]
    return BVHTree.FromPolygons(points, faces, all_triangles=True, epsilon=1e-9)


RAY_DIRECTIONS = [Vector(v).normalized() for v in
                  ((.937, .271, .221), (-.317, .889, .329), (.271, -.417, .867))]


def contains_point(tree, point, boundary_tolerance_m=2e-6):
    """Three-direction parity vote avoids a single grazing-edge ray failure."""
    nearest = tree.find_nearest(point)
    if nearest[0] is not None and nearest[3] <= boundary_tolerance_m:
        return True, float(nearest[3]), True
    votes = []
    for direction in RAY_DIRECTIONS:
        origin = point.copy()
        crossings = 0
        for _ in range(64):
            hit, _normal, _index, _distance = tree.ray_cast(origin, direction, 1.)
            if hit is None:
                break
            crossings += 1
            origin = hit+direction*2e-7
        else:
            raise AssertionError('Joint BVH ray did not leave a closed pommel component')
        votes.append(bool(crossings % 2))
    return sum(votes) >= 2, (float(nearest[3]) if nearest[0] is not None else math.inf), len(set(votes)) == 1


def wood_joint_audit(shaft, pommel):
    """Sample the actual faceted shaft surface inside the final gold fitting.

    Z sections are at most 1mm apart and include all source-ring levels and
    inter-level midpoints. Actual shaft-face boundary segments are sampled at
    most 0.5mm apart. This is a dense sampled surface check, not a proof over
    every point of a continuous union. No idealized circular shaft is used.
    """
    points = world_points(shaft)
    top = max(p.z for ob in pommel for p in world_points(ob))
    low = min(p.z for p in points)
    require(abs(top-.1281) < 1e-6 and low < top,
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
              'method': 'actual shaft face sections; three-direction BVH parity against union of three closed pommel meshes',
              'continuous_surface_proof': False, 'source_z_span_m': [low, top],
              'axial_sections': len(levels), 'maximum_axial_step_m': .001,
              'maximum_cross_section_step_m': .0005, 'boundary_tolerance_m': 2e-6,
              'samples': len(samples), 'outside_samples': len(outside),
              'ray_vote_disagreements': vote_disagreements,
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
    baseline = json.loads((WORK/'Baseline_Source_Components.json').read_text(encoding='utf-8'))
    protected = {name: row for name, row in baseline.items() if not name.startswith(PREFIXES)}
    require(len(protected) == 70, f'Expected 70 protected components, found {len(protected)}')
    require(set(objects) == set(protected)|EXPECTED_COMPONENTS,
            f'Source object set mismatch: added={sorted(set(objects)-set(protected)-EXPECTED_COMPONENTS)}, '
            f'missing={sorted((set(protected)|EXPECTED_COMPONENTS)-set(objects))}')
    checked = {}
    for name, row in protected.items():
        actual = fingerprint(objects[name])
        require(actual == row['fingerprint'], f'Protected component changed: {name}')
        checked[name] = actual
    report['protected_component_count'] = len(checked)
    report['protected_full_source_fingerprints'] = checked

    expected_textures = json.loads((WORK/'Protected_Texture_Hashes.json').read_text(encoding='utf-8'))
    actual_texture_paths = {p.name: p for p in (OUT/'Textures').glob('T_ImperialSpear_*.png')}
    require(set(actual_texture_paths) == set(expected_textures), 'Protected atlas file set changed')
    actual_hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in actual_texture_paths.items()}
    require(actual_hashes == expected_textures, f'Protected atlas bytes changed: '
            f'{[name for name in expected_textures if actual_hashes[name] != expected_textures[name]]}')
    report['all_atlas_file_hashes_unchanged'] = actual_hashes

    pommel = [objects[name] for name in sorted(EXPECTED_COMPONENTS)]
    report['pommel_components'] = {}
    for ob in pommel:
        row, _planes = mesh_audit(ob)
        require(ob.get('PommelDesign') == 'flattened_leaf', f'Missing design marker: {ob.name}')
        require(len(ob.data.uv_layers) == 1 and ob.data.uv_layers[0].name == 'UV0_SurfaceAtlas',
                f'Unexpected source UV layout: {ob.name}')
        require(len(ob.data.corner_normals) == len(ob.data.loops) and
                all(c.vector.length > .5 and all(math.isfinite(v) for v in c.vector) for c in ob.data.corner_normals),
                f'Invalid source custom normals: {ob.name}')
        require(all(math.isfinite(v) for item in ob.data.uv_layers[0].data for v in item.uv),
                f'Nonfinite source UV: {ob.name}')
        uv = ob.data.uv_layers[0].data
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
    require(specs is not None and len(specs) == 3, 'Leaf collision helper did not resolve three sections')
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
    require(bounds_error < 2e-6 and abs(source_bounds['min'][2]) < 1e-6
            and abs(source_bounds['max'][2]-2.2) < 1e-6, 'Source/GAME length, pivot or bounds changed')
    report['source_game_comparison'] = {'source_objects': len(objects),
        'source_triangles': source_triangles, 'game_triangles': game_triangles,
        'source_vertices': source_vertices, 'game_vertices': len(render.data.vertices),
        'pommel_triangles': sum(triangles(ob) for ob in pommel),
        'protected_triangles': sum(baseline[name]['triangles'] for name in protected),
        'source_bounds_m': source_bounds, 'game_bounds_grip_relative_m': game_bounds,
        'maximum_bounds_error_m': bounds_error, 'overall_length_m': 2.2, 'grip_from_pommel_m': GRIP}
    shafts = [ob for ob in objects.values() if ob.name.startswith('01 •')]
    require(len(shafts) == 1, f'Expected one protected wood shaft, found {len(shafts)}')
    wood_joint_audit(shafts[0], pommel)
    report['status'] = 'LEAF_POMMEL_SOURCE_AND_ACTUAL_GAME_COLLISION_AUDITED'


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
