"""Fit a small explicit hull using original surface vertices, avoiding thin synthetic facets."""
import json
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull
from scipy.optimize import minimize, LinearConstraint

folder = Path(__file__).resolve().parent
source = json.loads((folder / 'source.json').read_text())
vertices = np.array(source['vertices_cm'])
original = ConvexHull(vertices)
extreme = vertices[original.vertices]
selected = list(dict.fromkeys([int(f(extreme[:, a])) for a in range(3) for f in (np.argmin, np.argmax)]))
for _ in range(122):
    points = extreme[selected]
    hull = ConvexHull(points)
    outside = (extreme @ hull.equations[:, :3].T + hull.equations[:, 3]).max(axis=1)
    index = int(outside.argmax())
    if outside[index] <= .025:
        break
    assert index not in selected
    selected.append(index)
assert len(points) <= 128
constraint = LinearConstraint(hull.equations[:, :3], -np.inf, -hull.equations[:, 3])
distances = []
for p in extreme:
    projection = minimize(lambda x: .5*np.dot(x-p, x-p), p, jac=lambda x:x-p,
                          constraints=[constraint], method='SLSQP', options={'ftol':1e-13, 'maxiter':200})
    assert projection.success, projection.message
    distances.append(float(np.linalg.norm(projection.x-p)))
assert max(distances) < .20
job = {'asset':source['asset'], 'source_vertices':vertices.tolist(), 'hull_vertices':points.tolist()}
(folder/'job.json').write_text(json.dumps(job, indent=2))
report = {'asset':source['asset'], 'source_vertices':len(vertices), 'hull_vertices':len(points),
          'source_convex_vertices':len(extreme), 'max_inward_surface_difference_mm':10*max(distances),
          'outward_surface_difference_mm':0, 'source_bounds_preserved':bool(np.array_equal(vertices.min(0),points.min(0)) and np.array_equal(vertices.max(0),points.max(0))),
          'original_volume_cm3':original.volume, 'new_volume_cm3':hull.volume,
          'volume_change_percent':100*(hull.volume/original.volume-1),
          'scope':'Explicit subset of original source surface vertices. No adapter tolerance/cap changes.'}
(folder/'surface_geometry_report.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
