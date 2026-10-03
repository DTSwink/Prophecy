"""Author one explicit conservative low-vertex collision hull for this sword asset only."""
import json
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull, HalfspaceIntersection
from scipy.optimize import minimize, LinearConstraint
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

folder = Path(__file__).resolve().parent
source = json.loads((folder / 'source.json').read_text())
vertices = np.array(source['vertices_cm'], dtype=float)
original = ConvexHull(vertices)
planes = original.equations.copy()
padding = 0.00005  # cm; protects source coverage after float serialization/cooking.
planes[:, 3] -= padding
center = vertices[original.vertices].mean(axis=0)
selected = []
for axis in range(3):
    for sign in (-1, 1):
        normal = np.zeros(3); normal[axis] = sign
        selected.append(np.r_[normal, -np.max(vertices @ normal) - padding])

history = []
for iteration in range(60):
    halfspaces = np.array(selected)
    points = HalfspaceIntersection(halfspaces, center).intersections
    hull = ConvexHull(points)
    points = points[hull.vertices]
    violations = points @ planes[:, :3].T + planes[:, 3]
    worst = np.unravel_index(np.argmax(violations), violations.shape)
    error = float(violations[worst])
    history.append({'planes': len(selected), 'vertices': len(points), 'max_plane_error_cm': error})
    if error <= 0.13:
        break
    selected.append(planes[worst[1]])
else:
    raise RuntimeError('Requested simple hull fit did not converge below the vertex budget')
assert 4 <= len(points) <= 128

# Independent nearest-point checks, in centimeters, bound outward error at each candidate extreme.
constraint = LinearConstraint(original.equations[:, :3], -np.inf, -original.equations[:, 3])
distances = []
for point in points:
    projection = minimize(lambda x: 0.5 * np.dot(x-point, x-point), point,
                          jac=lambda x: x-point, constraints=[constraint], method='SLSQP',
                          options={'ftol': 1e-13, 'maxiter': 200})
    assert projection.success, projection.message
    distances.append(float(np.linalg.norm(projection.x-point)))
new_hull = ConvexHull(points)
coverage = vertices @ new_hull.equations[:, :3].T + new_hull.equations[:, 3]
assert float(coverage.max()) <= 1e-7
assert max(distances) < 0.20, max(distances)

job = {'asset': source['asset'], 'source_vertices': vertices.tolist(), 'hull_vertices': points.tolist()}
(folder / 'job.json').write_text(json.dumps(job, indent=2))
report = {'asset': source['asset'], 'source_vertices': len(vertices),
          'original_source_hull_vertices': len(original.vertices), 'new_hull_vertices': len(points),
          'max_outward_surface_error_mm': max(distances)*10,
          'max_source_plane_violation_cm': float(coverage.max()),
          'original_convex_volume_cm3': original.volume, 'new_convex_volume_cm3': new_hull.volume,
          'volume_change_percent': 100*(new_hull.volume/original.volume-1),
          'source_bounds_cm': [vertices.min(axis=0).tolist(), vertices.max(axis=0).tolist()],
          'candidate_bounds_cm': [points.min(axis=0).tolist(), points.max(axis=0).tolist()],
          'history': history,
          'scope': 'One explicitly authored convex, conservative relative to the actual source mesh convex envelope; visible geometry unchanged.'}
(folder / 'geometry_report.json').write_text(json.dumps(report, indent=2))

fig, axes = plt.subplots(1, 2, figsize=(8, 10), facecolor='#f6f7f9')
for ax, horizontal, title in zip(axes, (1, 0), ('Front silhouette', 'Thickness profile')):
    ax.set_facecolor('#f6f7f9')
    ax.scatter(vertices[:, horizontal], vertices[:, 2], s=3, c='#596273', alpha=.55, label='Visible mesh vertices')
    projection = points[:, [horizontal, 2]]
    boundary = projection[ConvexHull(projection).vertices]
    boundary = np.vstack([boundary, boundary[0]])
    ax.plot(boundary[:, 0], boundary[:, 1], c='#e25c33', lw=1.5, label='New collision hull')
    ax.set_aspect('equal'); ax.set_title(title); ax.set_xlabel('cm'); ax.set_ylabel('cm')
    ax.grid(alpha=.15); ax.legend(loc='upper right', fontsize=8)
fig.suptitle(f'Training sword: {len(points)}-vertex collision hull\nVisible mesh unchanged; maximum outward difference {max(distances)*10:.3f} mm', fontsize=13)
fig.tight_layout(rect=[0, 0, 1, .94])
fig.savefig(folder / 'hull_preview.png', dpi=150)
print(json.dumps({k:v for k,v in report.items() if k != 'history'}, indent=2))
