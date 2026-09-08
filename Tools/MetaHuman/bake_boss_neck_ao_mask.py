"""Bake a linear head-only collar surface-distance texture, without source edits.

Run in background Blender with bossfinalsave.blend open. Output is procedural
16-bit grayscale PNG data: saturate(surface edge distance / 0.10 meters).
For the requested shader: saturate((sample * 10cm - 0.2cm) / 5cm).
No geometry, normal, material, skin-weight, UV or rig edits; no blend save.
"""
import hashlib
import heapq
import json
import math
import struct
import sys
import zlib
from collections import defaultdict
from pathlib import Path

import bpy
import numpy as np
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from boss_collar_normals import _ring

SIZE = 1024
DISTANCE_RANGE_M = 0.10
DILATION_PX = 16
HEAD_MATERIAL = 6
OUT = Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/BossShading/20260908/NeckFade')
OUTPUT = OUT / 'T_Boss_NeckDistance.png'
REPORT = OUT / 'T_Boss_NeckDistance.json'


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_state(obj):
    mesh = obj.data
    payload = {
        'positions': [tuple(v.co) for v in mesh.vertices],
        'weights': [tuple((g.group, g.weight) for g in v.groups) for v in mesh.vertices],
        'uvs': [[tuple(d.uv) for d in layer.data] for layer in mesh.uv_layers],
        'polygons': [(tuple(p.vertices), p.material_index, p.use_smooth) for p in mesh.polygons],
        'normals': [tuple(n.vector) for n in mesh.corner_normals],
        'matrix_world': [tuple(row) for row in obj.matrix_world],
        'rigs': {a.name: [(b.name, [tuple(r) for r in b.matrix_local]) for b in a.data.bones]
                 for a in bpy.data.objects if a.type == 'ARMATURE'},
    }
    return hashlib.sha256(json.dumps(payload, separators=(',', ':')).encode()).hexdigest()


def _png16gray(path, values):
    # No sRGB or gamma chunk: this is data, not display-referred color.
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag+data) & 0xffffffff)
    encoded = np.rint(np.clip(values, 0.0, 1.0)*65535.0).astype('>u2')
    raw = b''.join(b'\x00'+row.tobytes() for row in encoded)
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', SIZE, SIZE, 16, 0, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw, 9))
    png += chunk(b'IEND', b'')
    path.write_bytes(png)
    return encoded.astype(np.float64)/65535.0


def _sample(values, uv):
    x = min(max(uv[0]*SIZE-0.5, 0.0), SIZE-1.0)
    y = min(max((1.0-uv[1])*SIZE-0.5, 0.0), SIZE-1.0)
    x0, y0 = int(x), int(y)
    x1, y1 = min(x0+1, SIZE-1), min(y0+1, SIZE-1)
    fx, fy = x-x0, y-y0
    return float((values[y0,x0]*(1-fx)+values[y0,x1]*fx)*(1-fy)
                 +(values[y1,x0]*(1-fx)+values[y1,x1]*fx)*fy)


def _stats(values):
    return {'count': len(values), 'min': min(values) if values else None,
            'max': max(values) if values else None,
            'mean': sum(values)/len(values) if values else None}


def main():
    source = Path(bpy.data.filepath)
    source_sha = _sha(source)
    obj = bpy.data.objects['boss']
    bpy.context.view_layer.update()
    state_before = _source_state(obj)
    mesh = obj.data
    world = [obj.matrix_world@v.co for v in mesh.vertices]
    uv_layer = mesh.uv_layers[0]
    edge_faces = defaultdict(list)
    adjacency = defaultdict(dict)
    head_vertices = set()
    head_loops = defaultdict(list)
    for polygon in mesh.polygons:
        for edge in polygon.edge_keys:
            a,b = tuple(sorted(edge))
            edge_faces[(a,b)].append(polygon.index)
            if polygon.material_index == HEAD_MATERIAL:
                distance = (world[a]-world[b]).length
                adjacency[a][b] = distance
                adjacency[b][a] = distance
        if polygon.material_index == HEAD_MATERIAL:
            head_vertices.update(polygon.vertices)
            for li in polygon.loop_indices:
                head_loops[mesh.loops[li].vertex_index].append(li)
    collar = _ring([edge for edge,faces in edge_faces.items()
                    if len(faces)==1 and mesh.polygons[faces[0]].material_index==HEAD_MATERIAL])
    distances = {v: math.inf for v in head_vertices}
    pending = [(0.0, v) for v in collar]
    heapq.heapify(pending)
    for v in collar:
        distances[v] = 0.0
    while pending:
        distance,vertex = heapq.heappop(pending)
        if distance != distances[vertex]:
            continue
        for neighbor,length in adjacency[vertex].items():
            new_distance = distance+length
            if new_distance < distances[neighbor]:
                distances[neighbor] = new_distance
                heapq.heappush(pending, (new_distance,neighbor))
    if any(not math.isfinite(d) for d in distances.values()):
        raise RuntimeError('Head topology includes vertices disconnected from collar')

    mesh.calc_loop_triangles()
    raster_distance = np.full((SIZE,SIZE), np.inf, dtype=np.float64)
    covered = np.zeros((SIZE,SIZE), dtype=bool)
    overlap_disagreements = 0
    degenerate_uv_triangles = 0
    outside_uv_triangles = 0
    head_triangles = 0
    for tri in mesh.loop_triangles:
        if mesh.polygons[tri.polygon_index].material_index != HEAD_MATERIAL:
            continue
        head_triangles += 1
        uv = np.asarray([tuple(uv_layer.data[li].uv) for li in tri.loops], dtype=np.float64)
        if uv.min() < -1e-5 or uv.max() > 1.00001:
            outside_uv_triangles += 1
        coords = np.column_stack((uv[:,0]*SIZE-0.5, (1-uv[:,1])*SIZE-0.5))
        lo = np.maximum(np.ceil(coords.min(axis=0)).astype(int), 0)
        hi = np.minimum(np.floor(coords.max(axis=0)).astype(int), SIZE-1)
        if np.any(lo>hi):
            continue
        a,b,c = coords
        denom = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(denom)<1e-10:
            degenerate_uv_triangles += 1
            continue
        yy,xx = np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
        wa = ((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/denom
        wb = ((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/denom
        wc = 1-wa-wb
        inside = (wa>=-1e-8)&(wb>=-1e-8)&(wc>=-1e-8)
        d = wa*distances[tri.vertices[0]]+wb*distances[tri.vertices[1]]+wc*distances[tri.vertices[2]]
        r = raster_distance[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
        overlap_disagreements += int(np.count_nonzero(inside&np.isfinite(r)&(np.abs(d-r)>0.002)))
        r[inside] = np.minimum(r[inside], d[inside])
        covered[lo[1]:hi[1]+1,lo[0]:hi[0]+1] |= inside
    if overlap_disagreements or outside_uv_triangles:
        raise RuntimeError(f'Unsafe head UV layout: {overlap_disagreements} conflicting raster samples; {outside_uv_triangles} outside-tile triangles')
    mask = np.ones((SIZE,SIZE), dtype=np.float64)
    mask[covered] = np.clip(raster_distance[covered]/DISTANCE_RANGE_M, 0,1)
    # Exact nearest covered texel for at least a 16-pixel band. Query only
    # uncovered pixels near the boundary; no scipy or full-image O(N^2) search.
    interior = covered.copy()
    interior[1:,:] &= covered[:-1,:]
    interior[:-1,:] &= covered[1:,:]
    interior[:,1:] &= covered[:,:-1]
    interior[:,:-1] &= covered[:,1:]
    boundary_y,boundary_x = np.nonzero(covered&~interior)
    tree = KDTree(len(boundary_x))
    for index,(x,y) in enumerate(zip(boundary_x,boundary_y)):
        tree.insert((float(x),float(y),0.0),index)
    tree.balance()
    expanded=covered.copy()
    for _ in range(DILATION_PX):
        prev=expanded.copy()
        expanded[1:,:] |= prev[:-1,:]
        expanded[:-1,:] |= prev[1:,:]
        expanded[:,1:] |= prev[:,:-1]
        expanded[:,:-1] |= prev[:,1:]
        expanded[1:,1:] |= prev[:-1,:-1]
        expanded[:-1,:-1] |= prev[1:,1:]
        expanded[1:,:-1] |= prev[:-1,1:]
        expanded[:-1,1:] |= prev[1:,:-1]
    dilation_count=0
    ys,xs=np.nonzero(expanded&~covered)
    for x,y in zip(xs,ys):
        _,index,distance=tree.find((float(x),float(y),0.0))
        if distance<=DILATION_PX:
            mask[y,x]=mask[boundary_y[index],boundary_x[index]]
            dilation_count+=1
    OUT.mkdir(parents=True,exist_ok=True)
    encoded=_png16gray(OUTPUT,mask)
    collar_samples=[]
    interior_samples=[]
    beyond_samples=[]
    for vertex in head_vertices:
        samples=[_sample(encoded,uv_layer.data[li].uv) for li in head_loops[vertex]]
        if vertex in collar:
            collar_samples.extend(samples)
        if distances[vertex]>=0.055:
            beyond_samples.extend([max(0.0,min(1.0,(v*0.10-0.002)/0.05)) for v in samples])
        if distances[vertex]>=0.10:
            interior_samples.extend(samples)
    if state_before!=_source_state(obj) or source_sha!=_sha(source):
        raise RuntimeError('Source state unexpectedly changed')
    shader_collar=[max(0.0,min(1.0,(v*0.10-0.002)/0.05)) for v in collar_samples]
    report={
        'source':str(source),'source_sha256':source_sha,'source_unchanged':True,
        'output':str(OUTPUT),'output_sha256':_sha(OUTPUT),'resolution':[SIZE,SIZE],
        'png_bits_per_channel':16,'png_channels':1,'color_space':'linear data; import with sRGB disabled',
        'encoding':'saturate(surface_edge_distance_m / 0.10)',
        'shader_expression':'saturate((sample * 10.0cm - 0.2cm) / 5.0cm)',
        'uv_layer':uv_layer.name,'head_material_source_index':HEAD_MATERIAL,
        'collar_vertex_count':len(collar),'head_vertex_count':len(head_vertices),
        'head_triangle_count':head_triangles,'degenerate_uv_triangles':degenerate_uv_triangles,
        'conflicting_uv_samples':overlap_disagreements,'covered_texels':int(covered.sum()),
        'nearest_texel_dilation_radius_px':DILATION_PX,'dilated_texels':dilation_count,
        'off_surface_background':1.0,'collar_geometric_distance_m':0.0,
        'collar_bilinear_texture_samples':_stats(collar_samples),
        'collar_shader_fade_samples':_stats(shader_collar),
        'surface_beyond_5_5cm_shader_fade':_stats(beyond_samples),
        'surface_beyond_10cm_texture_samples':_stats(interior_samples),
        'distance_range_m':_stats(list(distances.values())),
        'quantization_max_distance_error_mm':DISTANCE_RANGE_M*1000/65535/2,
        'geometry_uv_weights_materials_normals_rig_unchanged':True,
    }
    REPORT.write_text(json.dumps(report,indent=2))
    print('BOSS_NECK_DISTANCE_MASK '+json.dumps(report))


if __name__=='__main__':
    main()
