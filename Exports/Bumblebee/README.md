# Bumblebee (white-tailed): game-ready assets + ambient swarm

Real-world scale (about 2.5 cm long, about 3 cm wingspan), units cm, faces +X. Built procedurally in Blender 5.2 (headless).

## One-step setup
Run `setup_bumblebee.py` (editor: Tools > Execute Python Script, or headless:
`UnrealEditor-Cmd.exe GameAnimationSample3.uproject /Engine/Maps/Entry -ExecutePythonScript="Exports/Bumblebee/setup_bumblebee.py" -BeeSetupQuit -unattended -nullrhi -nocef -nosplash`).
It creates `/Game/Prophecy/Creatures/Bumblebee` (textures, 3 materials, skeletal hero mesh + anims, instanced swarm meshes) and only touches that folder.
`import_bumblebee_ue.py` from the first delivery is superseded by this script.

Then drop **Bumblebee Zone** actors (C++ class in the `ProphecyAmbient` module) on the map; see `Docs/Bumblebees.md`.

## Files
| File | What |
|---|---|
| `SK_Bumblebee.fbx`, `_LOD1`, `_LOD2` | hero skeletal mesh, 30 bones, anims `Fly` (60 f @ 60 fps) and `Idle_Landed` (120 f) |
| `Static/SM_Bumblebee_Fly_LOD0-3.fbx` | swarm mesh, flying pose (origin = body centre) |
| `Static/SM_Bumblebee_Landed_LOD0-3.fbx` | swarm mesh, landed pose (origin = between the feet on the surface) |
| `T_Bumblebee_*` | 1K body BC/N/ORM, fur-card atlas BC(A)/N, wing BC(A). Normals are DirectX |
| `Bumblebee_Source.blend` | editable source |

Static mesh vertex colours drive the material animation: R fur self-shadow, G wing id (1 fore, 0.5 hind), B leg weight, A tripod group.

## Budget
LOD0 18,060 / LOD1 7,218 / LOD2 2,532 / LOD3 355 tris; 3 materials (Body opaque, Fur masked one-sided back-to-back cards, Wing translucent).
