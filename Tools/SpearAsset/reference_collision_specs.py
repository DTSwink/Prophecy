"""Small conservative collision point sets for reference assembly revision2.

Pure Python geometry helpers; no bpy import or scene mutation. The exporter
passes editable objects in and receives grip-relative point sets/metadata.
The tassel, cord and beads are intentionally absent. The small eye opening is
filled in collision; the split casting retains its larger hooked silhouette.
"""
from __future__ import annotations

import math
from itertools import combinations


def world_vertices(ob):
    return [tuple(ob.matrix_world @ v.co) for v in ob.data.vertices]


def bounds(points):
    return {"min": [min(p[i] for p in points) for i in range(3)],
            "max": [max(p[i] for p in points) for i in range(3)]}


def matching(objects, prefix):
    result = [o for o in objects if o.type == "MESH" and o.name.startswith(prefix)]
    if not result:
        raise ValueError(f"Missing reference collision source: {prefix}")
    return result


def radial(z0, r0, z1, r1, grip, sides=12):
    # Circumscribed polygon: contact planes do not cut inside a round shaft.
    factor = 1 / math.cos(math.pi / sides)
    return [(r*factor*math.cos(j*math.tau/sides), r*factor*math.sin(j*math.tau/sides), z-grip)
            for z,r in ((z0,r0),(z1,r1)) for j in range(sides)]


def axial_profile(ob):
    points = world_vertices(ob)
    bb = bounds(points)
    cx,cy = [(bb["min"][i]+bb["max"][i])*.5 for i in (0,1)]
    if max(abs(cx),abs(cy)) > .0005:
        raise ValueError(f"Lathed collider is unexpectedly off-axis: {ob.name}")
    levels = {}
    for x,y,z in points:
        key = round(z,7)
        levels[key] = max(levels.get(key,0), math.hypot(x-cx,y-cy))
    return sorted(levels.items()), bb


def profile_envelope(ob, grip, sides=12):
    """Five axial stations, <=60 hull input vertices, enclosing source radii."""
    profile,bb = axial_profile(ob)
    low,high = profile[0][0],profile[-1][0]
    if high-low < .0001:
        raise ValueError(f"Degenerate ring/socket axial extent: {ob.name}")
    def radius(z):
        for (a,ra),(b,rb) in zip(profile,profile[1:]):
            if a <= z <= b:
                t=(z-a)/(b-a)
                return ra*(1-t)+rb*t
        return profile[-1][1]
    zs=[low+(high-low)*f for f in (0,.22,.5,.78,1)]
    rs=[radius(z)+.00010 for z in zs]
    # Raise adjacent stations only where their chord would cut into a convex
    # bulge. This keeps the actual asymmetrical ring profile, not a cylinder.
    for z,r in profile:
        for i in range(len(zs)-1):
            if zs[i] <= z <= zs[i+1]:
                t=(z-zs[i])/(zs[i+1]-zs[i])
                deficit=r+.00010-(rs[i]*(1-t)+rs[i+1]*t)
                if deficit > 0:
                    rs[i]+=deficit;rs[i+1]+=deficit
                break
    factor=1/math.cos(math.pi/sides)
    coords=[(r*factor*math.cos(j*math.tau/sides),r*factor*math.sin(j*math.tau/sides),z-grip)
            for z,r in zip(zs,rs) for j in range(sides)]
    return coords,{"source_bounds_m":bb,"axial_envelope_profile_m":list(zip(zs,rs)),
                   "circumferential_sides":sides,"profile_source":ob.name}


def slab_points(objects, axis, low, high):
    """Include boundary crossings so convex halves meet without missing slivers."""
    result=[]
    for ob in objects:
        points=world_vertices(ob)
        result.extend(p for p in points if low-1e-9 <= p[axis] <= high+1e-9)
        for edge in ob.data.edges:
            a,b=[points[index] for index in edge.vertices]
            for plane in (low,high):
                if not math.isfinite(plane) or (a[axis]-plane)*(b[axis]-plane) >= 0:
                    continue
                t=(plane-a[axis])/(b[axis]-a[axis])
                p=tuple(a[i]+t*(b[i]-a[i]) for i in range(3))
                if low-1e-9 <= p[axis] <= high+1e-9:
                    result.append(p)
    if len(result)<4:
        raise ValueError("Casting split contains insufficient geometry")
    return result


def plate_envelope(points, grip, directions=16):
    """Intersection of16 enclosing XZ support planes, extruded in Y (32 verts)."""
    normals=[(math.cos(j*math.tau/directions),math.sin(j*math.tau/directions)) for j in range(directions)]
    support=[max(nx*p[0]+nz*p[2] for p in points)+.00015 for nx,nz in normals]
    polygon=[]
    for i,(a,b) in enumerate(normals):
        j=(i+1)%directions;c,d=normals[j]
        determinant=a*d-b*c
        polygon.append(((support[i]*d-b*support[j])/determinant,
                        (a*support[j]-support[i]*c)/determinant))
    ymin=min(p[1] for p in points)-.00015;ymax=max(p[1] for p in points)+.00015
    return [(x,y,z-grip) for x,z in polygon for y in (ymin,ymax)]


def pommel_slab_points(objects, low, high):
    """Enclose source faces clipped to a Z slab, including tessellation cuts.

    In addition to original vertices, every face chord crossing a slab plane
    contributes its intersection. Therefore any triangulation of a source
    polygon is covered, including an internal diagonal of a non-planar quad.
    Keep this separate from slab_points so accepted head hulls are unchanged.
    """
    result = []
    for ob in objects:
        points = world_vertices(ob)
        result.extend(p for p in points if low-1e-9 <= p[2] <= high+1e-9)
        for polygon in ob.data.polygons:
            indices = list(polygon.vertices)
            zs = [points[index][2] for index in indices]
            for plane in (low, high):
                if not min(zs) < plane < max(zs):
                    continue
                for ia, ib in combinations(indices, 2):
                    a, b = points[ia], points[ib]
                    if (a[2]-plane)*(b[2]-plane) >= 0:
                        continue
                    t = (plane-a[2])/(b[2]-a[2])
                    result.append(tuple(a[i]+t*(b[i]-a[i]) for i in range(3)))
    result = list(dict.fromkeys(tuple(round(v, 12) for v in p) for p in result))
    if len(result) < 4:
        raise ValueError(f"Pommel slab {low:g}..{high:g} has insufficient source geometry")
    return result


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _unit(vector):
    length = math.sqrt(_dot(vector, vector))
    return tuple(v/length for v in vector)


def envelope_containment_report(points, planes, tolerance_m=1e-7):
    """Check points against convex face planes, in the same coordinate frame.

    Each plane is (outward_unit_normal, offset), with dot(normal, p)<=offset.
    The exporter can also pass actual UCX polygon planes here for an independent
    post-convex-hull check. Positive violation means the source protrudes.
    """
    if not points or len(planes) < 4:
        raise ValueError("Containment requires source points and a closed convex plane set")
    if not all(math.isfinite(value) for p in points for value in p):
        raise ValueError("Nonfinite source point in collision containment check")
    for normal, offset in planes:
        if (not all(math.isfinite(v) for v in (*normal, offset))
                or abs(_dot(normal, normal)-1) > 1e-6):
            raise ValueError("Containment plane must have a finite unit normal")
    violation = float(max(_dot(normal, p)-offset for normal, offset in planes for p in points))
    return {"source_contained": violation <= tolerance_m,
            "sample_count": len(points), "max_plane_violation_m": violation,
            "minimum_plane_clearance_m": -violation,
            "tolerance_m": tolerance_m}


def fitted_pommel_envelope(points, grip, padding_m=.00015):
    """Fit a small 3D convex polytope to a flattened pommel section.

    Thirty outward support planes bound the source: twelve around its section,
    eight on each shoulder, and two axial caps. A bounded 3D polytope with at
    most 30 faces has at most 56 vertices, below Unreal's 64-vertex budget.
    Unlike a radial envelope this retains the leaf's distinct width/thickness.
    Enumerating every feasible triple-plane intersection constructs the full
    polytope, so the enclosing support planes also prove source containment.
    """
    if not points or not math.isfinite(padding_m) or padding_m < 0:
        raise ValueError("Invalid pommel envelope inputs")
    bb = bounds(points)
    centre = tuple((lo+hi)*.5 for lo, hi in zip(bb["min"], bb["max"]))
    radii = tuple((hi-lo)*.5 for lo, hi in zip(bb["min"], bb["max"]))
    if min(radii) < .00001:
        raise ValueError(f"Degenerate pommel section: {bb}")
    local = [tuple(p[i]-centre[i] for i in range(3)) for p in points]
    normals = [_unit((math.cos(j*math.tau/12)/radii[0],
                      math.sin(j*math.tau/12)/radii[1], 0)) for j in range(12)]
    normals += [_unit((math.cos(j*math.tau/8)/radii[0],
                       math.sin(j*math.tau/8)/radii[1], slope*.65/radii[2]))
                for slope in (-1, 1) for j in range(8)]
    normals += [(0., 0., -1.), (0., 0., 1.)]
    planes = [(n, max(_dot(n, p) for p in local)+padding_m) for n in normals]
    vertices = []
    for (a, ha), (b, hb), (c, hc) in combinations(planes, 3):
        bc, ca, ab = _cross(b, c), _cross(c, a), _cross(a, b)
        determinant = _dot(a, bc)
        if abs(determinant) < 1e-10:
            continue
        point = tuple((ha*bc[i]+hb*ca[i]+hc*ab[i])/determinant for i in range(3))
        if any(_dot(n, point)-h > 1e-9 for n, h in planes):
            continue
        if any(sum((point[i]-v[i])**2 for i in range(3)) < 1e-16 for v in vertices):
            continue
        vertices.append(point)
    if not 4 <= len(vertices) <= 56:
        raise ValueError(f"Pommel support-plane intersection produced {len(vertices)} vertices")
    coords = [tuple(p[i]+centre[i]-(grip if i == 2 else 0) for i in range(3))
              for p in vertices]
    grip_centre = (centre[0], centre[1], centre[2]-grip)
    grip_planes = [(n, h+_dot(n, grip_centre)) for n, h in planes]
    source_relative = [(p[0], p[1], p[2]-grip) for p in points]
    report = envelope_containment_report(source_relative, grip_planes)
    if not report["source_contained"]:
        raise ValueError(f"Pommel source protrudes from fitted envelope: {report}")
    report.update({"method": "source vertices and all clipped face-chord intersections",
                   "support_plane_count": len(planes), "hull_input_vertex_count": len(coords)})
    return coords, {"source_bounds_m": bb, "envelope_padding_m": padding_m,
                    "containment": report, "support_planes_grip_relative": grip_planes}


def flattened_pommel_specs(objects, grip):
    """Return three fitted sections for leaf/lotus designs, or None for old assets."""
    sources = [o for o in objects if o.type == "MESH" and o.name.startswith(("02 •", "Pommel •"))]
    markers = [o for o in sources if o.name.startswith(("02 • flattened leaf pommel","02 • carved lotus pommel body"))
               or getattr(o, "get", lambda key, default=None: default)("PommelDesign") in ("flattened_leaf","lotus_bud")]
    if not markers:
        return None
    # The body owns explicit slab cuts; don't depend on object creation order.
    marker = next((o for o in markers if o.name.startswith("02 •")),markers[0])
    prop = getattr(marker, "get", lambda key, default=None: default)
    lotus = prop("PommelDesign") == "lotus_bud"
    cut_low = float(prop("PommelCollisionSplitLowM", .004 if lotus else .017))
    cut_high = float(prop("PommelCollisionSplitHighM", .104))
    all_points = [p for ob in sources for p in world_vertices(ob)]
    low, high = min(p[2] for p in all_points), max(p[2] for p in all_points)
    if not low < cut_low < cut_high < high:
        raise ValueError(f"Invalid flattened-pommel slab cuts: {low}, {cut_low}, {cut_high}, {high}")
    result = []
    for role, z0, z1 in ((("pommel_lotus_bud" if lotus else "pommel_blunt_foot"), low, cut_low),
                         (("pommel_carved_leaf" if lotus else "pommel_flattened_leaf"), cut_low, cut_high),
                         ("pommel_socket", cut_high, high)):
        points = pommel_slab_points(sources, z0, z1)
        coords, metadata = fitted_pommel_envelope(points, grip)
        result.append({"role": role, "coords": coords,
                       "source_objects": [o.name for o in sources],
                       "source_z_slab_m": [z0, z1], **metadata})
    return result


def build_reference_collision_specs(art, grip):
    objects=list(art.objects)
    socket=matching(objects,"05 • long engraved socket")[0]
    body=matching(objects,"07 •")
    relief=[o for o in objects if o.type=="MESH" and o.name.startswith("Socket • continuous cast inverted S")]
    socket_points=world_vertices(socket);socket_low=min(p[2] for p in socket_points)
    if not 1.51 < socket_low < 1.55:
        raise ValueError(f"Unexpected reference socket start: {socket_low}")
    specs=[]
    def add(role,coords,sources=(),**metadata):
        if any(name.startswith("Tassel") for name in sources):
            raise ValueError("Cosmetic tassel cannot become rigid collision")
        if not all(math.isfinite(c) for p in coords for c in p):
            raise ValueError(f"Nonfinite collision coordinates: {role}")
        specs.append({"role":role,"coords":coords,"source_objects":list(sources),**metadata})
    add("lower_shaft",radial(.1271,.016,1.1039,.016,grip),[matching(objects,"01 •")[0].name])
    add("forward_grip",radial(1.104,.0205,1.3679,.0205,grip),[o.name for o in objects if o.name.startswith(("03 •","04 •","Grip •"))])
    add("upper_shaft",radial(1.368,.016,socket_low+.00010,.016,grip),[matching(objects,"01 •")[0].name])
    pommel_specs = flattened_pommel_specs(objects, grip)
    if pommel_specs is None:
        add("blunt_pommel",radial(0,.0115,.127,.018,grip),[o.name for o in objects if o.name.startswith(("02 •","Pommel •"))])
    else:
        for spec in pommel_specs:
            add(spec["role"], spec["coords"], spec["source_objects"],
                **{key: value for key, value in spec.items()
                   if key not in ("role", "coords", "source_objects")})
    coords,metadata=profile_envelope(socket,grip)
    add("engraved_socket",coords,[socket.name],**metadata)
    for prefix,role,expected in (("Socket • thin flared neck ring","neck_ring",1.666),
                                 ("Socket • broad asymmetrical","middle_ring",1.587),
                                 ("Socket • narrow terminal cuff","terminal_cuff",1.534)):
        ob=matching(objects,prefix)[0];coords,metadata=profile_envelope(ob,grip)
        bb=metadata["source_bounds_m"];centre=(bb["min"][2]+bb["max"][2])*.5
        if abs(centre-expected)>.015:
            raise ValueError(f"Unexpected current collar centre: {ob.name}: {centre}")
        add(role,coords,[ob.name],centre_z_m=centre,**metadata)
    for label,low,high in (("left",-math.inf,0),("right",0,math.inf)):
        points=slab_points(body+relief,0,low,high)
        add("cast_housing_"+label,plate_envelope(points,grip),[o.name for o in body+relief],
            source_bounds_m=bounds(points),eye_aperture_filled_for_simple_collision=True)
    crown=[o for o in objects if o.type=="MESH" and o.name.startswith("Blade • flame and compact unified casting")]
    if not crown:
        crown=matching(objects,"Blade • flame and compact cast spiral")
    points=[p for ob in crown for p in world_vertices(ob)]
    add("seated_flame_and_spiral",plate_envelope(points,grip),[o.name for o in crown],
        source_bounds_m=bounds(points),small_ornament_openings_filled_for_simple_collision=True)
    return specs
