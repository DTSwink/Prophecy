import json
import unreal


def prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


mesh = unreal.load_asset('/Game/_mygame/SKM_UEFN_Mannequin')
if mesh is None:
    raise RuntimeError('SKM_UEFN_Mannequin was not found')

physics_asset = prop(mesh, 'physics_asset')
if physics_asset is None:
    try:
        physics_asset = mesh.get_physics_asset()
    except Exception:
        physics_asset = None
if physics_asset is None:
    raise RuntimeError('SKM_UEFN_Mannequin has no Physics Asset')

try:
    subobjects = [obj for obj in unreal.ObjectIterator() if obj.get_outer() == physics_asset]
except Exception as exc:
    unreal.log_warning('PROPHECY_PHYSICS_ASSET_SUBOBJECT_ENUM_FAILED=' + repr(exc))
    subobjects = []

bodies = [obj for obj in subobjects if obj.get_class().get_name() == 'SkeletalBodySetup']
constraint_templates = [obj for obj in subobjects if obj.get_class().get_name() == 'PhysicsConstraintTemplate']
try:
    constraint_accessors = list(physics_asset.get_constraints(False))
except Exception as exc:
    unreal.log_warning('PROPHECY_PHYSICS_ASSET_CONSTRAINT_ENUM_FAILED=' + repr(exc))
    constraint_accessors = []

constraint_rows = []
for template in constraint_templates:
    instance = prop(template, 'default_instance')
    profile = prop(instance, 'profile_instance')
    constraint_rows.append({
        'joint': str(prop(instance, 'joint_name', '')),
        'parent': str(prop(instance, 'constraint_bone2', '')),
        'child': str(prop(instance, 'constraint_bone1', '')),
        'disable_collision': prop(profile, 'disable_collision'),
        'enable_projection': prop(profile, 'enable_projection'),
        'projection_linear_alpha': prop(profile, 'projection_linear_alpha'),
        'projection_angular_alpha': prop(profile, 'projection_angular_alpha'),
        'enable_mass_conditioning': prop(profile, 'enable_mass_conditioning'),
        'enable_shock_propagation': prop(profile, 'enable_shock_propagation'),
    })
body_rows = []
shape_totals = {'sphere': 0, 'box': 0, 'capsule': 0, 'tapered_capsule': 0, 'convex': 0, 'level_set': 0, 'skinned_level_set': 0}

for body in bodies:
    geom = prop(body, 'agg_geom')
    shape_counts = {
        'sphere': len(prop(geom, 'sphere_elems', []) or []),
        'box': len(prop(geom, 'box_elems', []) or []),
        'capsule': len(prop(geom, 'sphyl_elems', []) or []),
        'tapered_capsule': len(prop(geom, 'tapered_capsule_elems', []) or []),
        'convex': len(prop(geom, 'convex_elems', []) or []),
        'level_set': len(prop(geom, 'level_set_elems', []) or []),
        'skinned_level_set': len(prop(geom, 'skinned_level_set_elems', []) or []),
    }
    for key, value in shape_counts.items():
        shape_totals[key] += value
    instance = prop(body, 'default_instance')
    body_rows.append({
        'bone': str(prop(body, 'bone_name', '')),
        'physics_type': str(prop(body, 'physics_type', '')),
        'consider_for_bounds': bool(prop(body, 'consider_for_bounds', False)),
        'shapes': shape_counts,
        'collision_enabled': str(prop(instance, 'collision_enabled', '')),
        'use_ccd': bool(prop(instance, 'use_ccd', False)),
        'use_macd': bool(prop(instance, 'use_macd', False)),
        'override_iterations': bool(prop(instance, 'override_iteration_counts', False)),
        'position_iterations': prop(instance, 'position_solver_iteration_count'),
        'velocity_iterations': prop(instance, 'velocity_solver_iteration_count'),
        'projection_iterations': prop(instance, 'projection_solver_iteration_count'),
    })

result = {
    'mesh': mesh.get_path_name(),
    'physics_asset': physics_asset.get_path_name(),
    'body_count': len(body_rows),
    'constraint_count': len(constraint_accessors),
    'shape_totals': shape_totals,
    'bodies': body_rows,
    'constraints': constraint_rows,
    'subobject_classes': sorted({obj.get_class().get_name() for obj in subobjects}),
}
unreal.log('PROPHECY_PHYSICS_ASSET_AUDIT=' + json.dumps(result, separators=(',', ':')))
