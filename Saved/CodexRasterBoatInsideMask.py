import json
import os

from PIL import Image, ImageDraw


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_PATH = os.path.join(PROJECT_ROOT, "Saved", "CodexBoatInsideGeometry.json")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "Saved", "CodexGenerated", "BoatWaterMask")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "T_BoatInside_WaterMask.png")
METADATA_PATH = os.path.join(OUTPUT_DIR, "T_BoatInside_WaterMask.json")

FINAL_SIZE = 512
SUPERSAMPLE = 4
PADDING_CM = 4.0

with open(SOURCE_PATH, "r", encoding="utf-8") as source_file:
    source = json.load(source_file)

vertices = source["vertices"]
triangles = source["triangles"]

min_x = min(vertex[0] for vertex in vertices if vertex is not None) - PADDING_CM
max_x = max(vertex[0] for vertex in vertices if vertex is not None) + PADDING_CM
min_y = min(vertex[1] for vertex in vertices if vertex is not None) - PADDING_CM
max_y = max(vertex[1] for vertex in vertices if vertex is not None) + PADDING_CM
range_x = max_x - min_x
range_y = max_y - min_y

working_size = FINAL_SIZE * SUPERSAMPLE
mask = Image.new("L", (working_size, working_size), 0)
draw = ImageDraw.Draw(mask)

def pixel_from_local(position):
    x = (position[0] - min_x) / range_x * (working_size - 1)
    # Match the material's (LocalY - MinY) / SizeY mapping exactly.
    y = (position[1] - min_y) / range_y * (working_size - 1)
    return (x, y)

for triangle in triangles:
    points = [pixel_from_local(vertices[vertex_index]) for vertex_index in triangle]
    draw.polygon(points, fill=255)

mask = mask.resize((FINAL_SIZE, FINAL_SIZE), Image.Resampling.LANCZOS)
os.makedirs(OUTPUT_DIR, exist_ok=True)
mask.save(OUTPUT_PATH, optimize=True)

metadata = {
    "texture_path": OUTPUT_PATH,
    "mesh_path": source["mesh_path"],
    "local_min": [min_x, min_y],
    "local_max": [max_x, max_y],
    "local_inv_size": [1.0 / range_x, 1.0 / range_y],
    "resolution": FINAL_SIZE,
    "padding_cm": PADDING_CM,
    "inside_actor": source["inside_actor"],
    "ocean_actor": source["ocean_actor"],
}
with open(METADATA_PATH, "w", encoding="utf-8") as metadata_file:
    json.dump(metadata, metadata_file, indent=2)

print(json.dumps(metadata, indent=2))
