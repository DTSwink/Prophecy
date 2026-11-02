# Bumblebee (white-tailed): game-ready skeletal mesh

Built procedurally in Blender 5.2 (headless). Real-world scale: about 2.5 cm long, wingspan about 3 cm. Units are cm. The bee faces +X and its origin is at the body centre.

## Contents
| File | What |
|---|---|
| `SK_Bumblebee.fbx` | LOD0 skeletal mesh + skeleton + animations `Fly` (60 f @ 60 fps loop) and `Idle_Landed` (120 f loop) |
| `SK_Bumblebee_LOD1.fbx`, `_LOD2.fbx` | LOD meshes on the same skeleton |
| `T_Bumblebee_Body_BC/N/ORM.png` | 1K body set (normal is **DirectX**; ORM = AO, Roughness, Metal) |
| `T_Bumblebee_Fur_BC.png` (RGBA, A = opacity), `T_Bumblebee_Fur_N.png` | 1K fur-card atlas |
| `T_Bumblebee_Wing_BC.png` (RGBA, A = opacity) | wing venation/membrane |
| `Bumblebee_Source.blend` | editable source (rig, actions, materials) |
| `import_bumblebee_ue.py` | one-click UE 5.7 import + material build |

## Budget
| LOD | Tris | Notes |
|---|---|---|
| LOD0 | 18,060 | about 1,900 fur cards, hairy legs |
| LOD1 | 7,218 | 42% of cards, wider single-segment |
| LOD2 | 2,532 | sparse cards, decimated body |

There are 3 materials/draw calls (Body opaque, Fur masked, Wing translucent) and 30 bones: root, thorax, head, abdomen, 2×2 antenna, 4 wings and 18 leg bones (rigid skinning, 1 influence per vertex).

## Import into Unreal
**Scripted:** in the editor run `Tools > Execute Python Script…` → `import_bumblebee_ue.py`. It imports to `/Game/Prophecy/Creatures/Bumblebee` (edit `DEST` at the top of the script), creates the 3 materials, assigns them, adds LOD1/2 and sets screen sizes.

**Manual:** import `SK_Bumblebee.fbx` as a Skeletal Mesh with Normals = *Import Normals*, Vertex Color = *Replace*, Import Animations on, no physics asset. Then build the materials:
- **Fur**: Masked, clip 0.33, *one-sided*. BaseColor = `Fur_BC.rgb × VertexColor.R`, OpacityMask = `Fur_BC.a`, Normal = `Fur_N`, Roughness 0.5. The cards are modelled back-to-back with body-direction normals, so the fur shades like a volume. Do **not** make this material two-sided.
- **Body**: BC, Normal, ORM (R→AO, G→Roughness).
- **Wing**: Translucent, two-sided, *Surface Per-Pixel* lighting, Opacity = `Wing_BC.a`, Roughness 0.2.
- Normals are DirectX already, so leave *Flip Green* off.

## Tips
- The `Fly` wingbeat is a 15 Hz cycle (4 frames). Keep motion blur on and it reads as a blurred buzz, like in the reference photo.
- In `Idle_Landed` the feet sit about 0.8 cm below the origin. Offset the mesh component when you place it on a flower.
- For swarms, force LOD2, or use LOD2 as a Niagara mesh particle.
