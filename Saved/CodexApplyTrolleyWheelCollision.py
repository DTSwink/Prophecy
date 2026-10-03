import json
import math

import unreal


ASSET_PATH = "/Game/_mygame/assets/trolley/SM_Trolley_Wheel"
SIDES = 12


def add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def mul(a, scalar):
    return tuple(value * scalar for value in a)


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def normalized(a):
    length = math.sqrt(dot(a, a))
    if length <= 1.0e-8:
        raise RuntimeError("Cannot normalize a zero-length vector")
    return mul(a, 1.0 / length)


def fmt_vector(value):
    return "(X={:.9f},Y={:.9f},Z={:.9f})".format(*value)


def make_cylinder(name, center, axis, half_length, radius, sides=SIDES):
    reference = (0.0, 0.0, 1.0)
    if abs(dot(axis, reference)) > 0.9:
        reference = (0.0, 1.0, 0.0)
    radial_u = normalized(cross(axis, reference))
    radial_v = normalized(cross(axis, radial_u))

    vertices = []
    for end_sign in (-1.0, 1.0):
        end_center = add(center, mul(axis, half_length * end_sign))
        for index in range(sides):
            angle = 2.0 * math.pi * index / sides
            radial = add(
                mul(radial_u, radius * math.cos(angle)),
                mul(radial_v, radius * math.sin(angle)),
            )
            vertices.append(add(end_center, radial))

    indices = []
    for index in range(sides):
        next_index = (index + 1) % sides
        a = index
        b = next_index
        c = sides + next_index
        d = sides + index
        indices.extend((a, b, c, a, c, d))
    for index in range(1, sides - 1):
        indices.extend((0, index + 1, index))
        indices.extend((sides, sides + index, sides + index + 1))

    minimum = tuple(min(vertex[i] for vertex in vertices) for i in range(3))
    maximum = tuple(max(vertex[i] for vertex in vertices) for i in range(3))
    vertex_text = ",".join(fmt_vector(vertex) for vertex in vertices)
    index_text = ",".join(str(index) for index in indices)
    elem_text = (
        "(VertexData=(" + vertex_text + "),"
        "IndexData=(" + index_text + "),"
        "ElemBox=(Min=" + fmt_vector(minimum) + ",Max=" + fmt_vector(maximum) + ",IsValid=True),"
        "Transform=(Rotation=(X=0,Y=0,Z=0,W=1),Translation=(X=0,Y=0,Z=0),Scale3D=(X=1,Y=1,Z=1)),"
        "RestOffset=0,bIsGenerated=False,Name=\"" + name + "\","
        "bContributeToMass=True,CollisionEnabled=QueryAndPhysics)"
    )
    element = unreal.KConvexElem()
    if not element.import_text(elem_text):
        raise RuntimeError("Failed to create convex collision element " + name)
    return element, vertices


dirty_packages = {
    package.get_path_name()
    for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
}
if ASSET_PATH in dirty_packages:
    raise RuntimeError("SM_Trolley_Wheel became dirty before collision editing; refusing to overwrite unsaved work")

mesh = unreal.load_asset(ASSET_PATH)
if not mesh:
    raise RuntimeError("Could not load " + ASSET_PATH)

materials_before = [
    material.material_interface.get_path_name() if material.material_interface else None
    for material in mesh.get_editor_property("static_materials")
]
bounds_before = mesh.get_bounds()
triangles_before = mesh.get_num_triangles(0)

# These measurements come from the asset's own exported LOD0 geometry, in UE centimeters.
# Both wheels and the axle share this slightly tilted axis.
left_wheel_center = (-67.5871104002, -5.9035822749, 2.0757347345)
right_wheel_center = (50.2602294087, -0.7670283318, 1.4252126217)
axis = normalized(sub(right_wheel_center, left_wheel_center))

specifications = (
    ("Wheel_Left", left_wheel_center, 8.24565, 51.50),
    ("Wheel_Right", right_wheel_center, 8.24565, 51.50),
    ("Axle", (-8.6634457111, -3.3353041857, 1.7504747957), 72.42, 4.65),
)

elements = []
debug_bounds = []
for name, center, half_length, radius in specifications:
    element, vertices = make_cylinder(name, center, axis, half_length, radius)
    elements.append(element)
    debug_bounds.append({
        "name": name,
        "vertex_count": len(vertices),
        "minimum": [min(vertex[i] for vertex in vertices) for i in range(3)],
        "maximum": [max(vertex[i] for vertex in vertices) for i in range(3)],
    })

aggregate = unreal.KAggregateGeom()
aggregate.set_editor_property("convex_elems", elements)
body_setup = mesh.get_editor_property("body_setup")
body_setup.modify()
body_setup.set_editor_property("agg_geom", aggregate)
mesh.modify()

if not unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False):
    raise RuntimeError("Unreal failed to save SM_Trolley_Wheel")

subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
materials_after = [
    material.material_interface.get_path_name() if material.material_interface else None
    for material in mesh.get_editor_property("static_materials")
]
bounds_after = mesh.get_bounds()
result = {
    "asset": ASSET_PATH,
    "convex_count": subsystem.get_convex_collision_count(mesh),
    "simple_primitive_count": subsystem.get_simple_collision_count(mesh),
    "collision_complexity": str(subsystem.get_collision_complexity(mesh)),
    "materials_unchanged": materials_before == materials_after,
    "triangles_unchanged": triangles_before == mesh.get_num_triangles(0),
    "bounds_origin_before": [bounds_before.origin.x, bounds_before.origin.y, bounds_before.origin.z],
    "bounds_origin_after": [bounds_after.origin.x, bounds_after.origin.y, bounds_after.origin.z],
    "bounds_extent_before": [bounds_before.box_extent.x, bounds_before.box_extent.y, bounds_before.box_extent.z],
    "bounds_extent_after": [bounds_after.box_extent.x, bounds_after.box_extent.y, bounds_after.box_extent.z],
    "hulls": debug_bounds,
}
print("CODEX_COLLISION_RESULT=" + json.dumps(result))
