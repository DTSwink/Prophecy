"""Pure-data review proposal for the middle ring and reference-pose tassel.

This module imports no Blender API, changes no files or scene, and has no
top-level execution. Root may call its functions from an explicit Blender
mutation after review. Existing accepted blade/collar/grip geometry is outside
its scope.

The current middle ring starts in rebuild_reference_gold.py and receives the
1.17 axial stretch in refine_reference_surfaces.py. Its resulting axial extent
is +/- 0.011115 m, and its maximum radius is 0.0264 m. Read the actual object's
extents when installing; pass those values here to preserve them exactly.
Recreate through turn(), so its analytic normals match the NEW profile.
"""

import math
import random


def middle_ring_profile(center_z, half_width=0.011115,
                        crown_radius=0.0264, wood_foot=0.0188,
                        blade_foot=0.0192):
    """Return (z, radius) stations, preserving centre/bounds/max diameter.

    Positive Z points toward the blade. The broad crown shifts toward that
    side; the negative-Z side has a subordinate retaining lip, not a second
    equal-sized lobe. All radii scale with the passed crown radius; terminal
    feet remain caller-controlled. Pass to the existing turn(..., sides=40).
    """
    shape = [
        (-1.00, 0.0188),
        (-0.96, 0.0197),
        (-0.89, 0.0210),
        (-0.80, 0.0219),
        (-0.72, 0.0221),  # Small wood-facing retaining lip.
        (-0.64, 0.0219),
        (-0.57, 0.0219),  # Shallow shoulder, never a second deep valley.
        (-0.43, 0.0233),
        (-0.24, 0.0250),
        (-0.03, 0.02605),
        (0.16, 0.02640),  # Exact existing maximum radius.
        (0.35, 0.02615),
        (0.54, 0.02515),
        (0.72, 0.02340),
        (0.88, 0.02080),
        (1.00, 0.01920),
    ]
    scale = crown_radius / 0.0264
    result = [(center_z + t * half_width, r * scale) for t, r in shape]
    result[0] = (center_z - half_width, wood_foot)
    result[-1] = (center_z + half_width, blade_foot)
    return result


def _bezier(a, b, c, d, t):
    omt = 1.0 - t
    return tuple(omt**3*a[i] + 3*omt**2*t*b[i] +
                 3*omt*t*t*c[i] + t**3*d[i] for i in range(2))


def _envelope(t):
    # The current accepted reference fan envelope remains unchanged.
    top = _bezier((706, 314), (763, 314), (850, 330), (891, 345), t)
    bottom = _bezier((706, 321), (753, 344), (824, 392), (873, 411), t)
    return top, bottom


def _sweep(f, t):
    # A smooth monotone cross-fan warp adds coherent gentle curvature.
    # It vanishes on the two exterior boundaries and at both ends.
    warp = (0.010 * math.sin(math.pi*f) * math.sin(math.pi*t) *
            (math.sin(4.0*math.pi*f + 0.9) +
             0.30*math.sin(8.0*math.pi*f + 2.1)))
    return min(1.0, max(0.0, f + warp))


def tassel_samples(count=24, rows=13, seed=27102731):
    """Return nonregular ribbon samples inside the existing fan envelope.

    Same 24 bundles and 13 intervals as the active source. Unequal band widths,
    small unequal gaps, smooth coherent sweep, and 0-5% terminal shortening
    break the regular ruler-ray pattern. Exterior endpoint bundles retain the
    original overall extent. Existing separate upper wisps may remain.

    Every row supplies left/right reference pixels, actual atlas U fractions,
    lengthwise V, and a gentle out-of-plane depth. No geometry is created here.
    """
    rng = random.Random(seed)
    weights = [rng.uniform(0.70, 1.32) for _ in range(count)]
    total = sum(weights)
    edges = [0.0]
    for value in weights:
        edges.append(edges[-1] + value / total)
    edges[-1] = 1.0
    result = []
    for k in range(count):
        a, b = edges[k:k+2]
        # Dense gathered cords: most slots are occupied, without a repeated gap.
        gap_left = rng.uniform(0.015, 0.065)
        gap_right = rng.uniform(0.015, 0.065)
        left = a if k == 0 else a + (b-a)*gap_left
        right = b if k == count-1 else b - (b-a)*gap_right
        end_t = 1.0 if k in (0, count-1) else rng.uniform(0.952, 0.998)
        phase = rng.uniform(-0.7, 0.7)
        f_center = (left + right) * 0.5
        samples = []
        for j in range(rows+1):
            q = j / rows
            t = 0.012 + (end_t - 0.012) * q
            top, bottom = _envelope(t)
            # Fade band width only near its terminus; avoid identical blunt tips.
            fade = max(0.0, (q - 0.84) / 0.16)
            tip_scale = 1.0 - (0.18 + 0.12*math.sin(k*2.31)**2)*fade*fade
            u0 = f_center + (left-f_center)*tip_scale
            u1 = f_center + (right-f_center)*tip_scale
            f0, f1 = _sweep(u0, t), _sweep(u1, t)
            pixel_left = tuple(top[i] + (bottom[i]-top[i])*f0 for i in range(2))
            pixel_right = tuple(top[i] + (bottom[i]-top[i])*f1 for i in range(2))
            depth = (-0.009 + 0.00065*math.sin(math.pi*t)*
                     math.sin(f_center*7.3 + phase) +
                     0.00030*t*t*math.sin(f_center*12.7 + 0.8))
            samples.append({
                'left_px': pixel_left, 'right_px': pixel_right,
                'u_left': u0, 'u_right': u1, 'v': t,
                'depth_m': depth,
            })
        result.append({'index': k, 'end_fraction': end_t, 'samples': samples})
    return result


def tassel_mesh_data(ref3, count=24, rows=13, seed=27102731):
    """Return verts/faces/UVs for existing mesh(..., 'silk', uv, smooth=True).

    ref3 must be the active r3(pixel, depth) callback. Keeps the same two thin
    surfaces, row count and face count as the existing reference-silk bundles;
    no additional modelling density, no Blender imports, no scene mutation.
    """
    meshes = []
    for bundle in tassel_samples(count, rows, seed):
        samples = bundle['samples']
        vertices, faces, uvfaces = [], [], []
        for layer in (-1, 1):
            for row in samples:
                for edge in ('left_px', 'right_px'):
                    vertices.append(tuple(ref3(row[edge], row['depth_m'] + layer*0.00012)))
        one = len(samples)*2
        for layer in range(2):
            for j in range(rows):
                a = layer*one + j*2
                if layer == 0:
                    face = (a, a+1, a+3, a+2)
                    uv = [(samples[j]['u_left'], samples[j]['v']),
                          (samples[j]['u_right'], samples[j]['v']),
                          (samples[j+1]['u_right'], samples[j+1]['v']),
                          (samples[j+1]['u_left'], samples[j+1]['v'])]
                else:
                    face = (a+2, a+3, a+1, a)
                    uv = [(samples[j+1]['u_left'], samples[j+1]['v']),
                          (samples[j+1]['u_right'], samples[j+1]['v']),
                          (samples[j]['u_right'], samples[j]['v']),
                          (samples[j]['u_left'], samples[j]['v'])]
                faces.append(face)
                uvfaces.append(uv)
        meshes.append({'index': bundle['index'], 'vertices': vertices,
                       'faces': faces, 'uvfaces': uvfaces})
    return meshes
