IMPERIAL SPEAR — concept04 Lotus bud rebuild, October 28, 2026

CURRENT CHANGE
The user rejected the previous flattened-leaf model, selected Lotus bud and
clarified that the MAIN BODY must have a four-peaked flower cross-section.
The body now has four radial longitudinal ribs and four broad Bezier concave
scoops. Width and depth are comparable. At the belly its axis diameter is
49.00mm, diagonal valley radius12.973mm and scoop depth
below the straight chord joining adjacent peaks is4.351mm.
Rib crests are1.20mm wide with0.65mm chamfer depth; the sculpted section
transitions into circular necks beneath the fittings. Each scoop contains a
closed leaf-shaped inset, recessed0.55mm, with an integral stepped border and
0.10mm flat raised lip. Its tips close at source z18.0/101.0mm.
The lower seat has a straight land and stepped separator. Lotus bud V3 has six
recessed arched petals, flat lip lands and inner bevel steps, a seated root
shoulder and a beveled throat around the rounded terminal button.
Four closed pommel components use
14,984 triangles without live subdivisions or Booleans.
The other70 components retain exact geometry, UVs, custom normals, material
assignments and transforms. All original four atlas PNGs are byte-identical.
The pommel uses the same M_ImperialSpear_PBR material and existing plain gold
atlas region as the spearhead, as explicitly requested by the user.

FILES
ImperialSpear_Source.blend: editable components; accepted head camera retained.
ImperialSpear_Game.blend: combined mesh, simple collision and two LODs.
SM_ImperialSpear.fbx: render mesh,17 UCX hulls,4 sockets.
SM_ImperialSpear.glb: shared-material PBR preview; collision is in FBX.
SM_ImperialSpear_LOD1.fbx / LOD2.fbx: aligned distance meshes.
Preview_Pommel.png / Preview_Pommel_Detail.png / Preview_Pommel_Front.png:
current oblique, macro and front views. Preview_Full.png is refreshed.
Preview_Pommel_Diagonal.png: diagonal view of the three-dimensional body.
Preview_Pommel_End.png: isolated body end-on inspection of the four-peaked section.

SPECIFICATION
Overall length223.10cm; the bud extends3.1cm below the old cap. The shaft,
blade and grip did not move. +Z toward blade; grip pivot is126.60cm from
the new bud tip. Leather source span111.5–135.5cm is unchanged.
LOD triangles 46,836/25,758/13,114. One material. UV0 surface / UV1 lightmap.
17 convex collision hulls, max60 vertices each. Three fitted pommel hulls;
all other collision shapes preserved. Tassel/cord/beads excluded, no cloth rig.
Sockets: Grip, BladeTip, Pommel (actual new tip), Tassel.

UNREAL MATERIALS AND IMPORT
Import at scale1, retain grip pivot, import normals/tangents and verify length.
Use supplied UCX simple collision. Import LOD FBXs separately and tune distances.
The single M_ImperialSpear_PBR slot uses original4096px maps under Textures/.
It is opaque. Enable Two Sided for the thin tassel ribbons.
BaseColor sRGB ON -> Base Color; ORM sRGB OFF with alpha
retained: R=AO, G=Roughness, B=Metallic, A=Specular. Alpha is not opacity.
NormalDX uses Normalmap compression, sRGB OFF -> Normal; do not flip green again.
NormalGL is for Blender/glTF. FBX wiring does not replace manual UE connections.
The large pommel carvings are geometry. Gold shading comes from the same
unchanged material and atlas maps used on the accepted spearhead.

VERIFICATION
Pommel_Lotus_Verification.json is current. Closed surfaces, positive volume,
valid UVs/normals, protected source hashes and actual UCX containment pass.
The dense wood-join surface check passes; it is sampled, not a continuous proof.
Main/LOD FBX readback verifies positions, actual UV0, custom normals and material
assignments, plus all hulls/sockets and scale. Export_Verification.json is current.
Prior leaf/handle audits describe historical stages; the leaf result was rejected.
Unreal import, collision cooking, material appearance, contacts and CCD remain
untested. No Unreal/Play/Blueprint/lab state changed. Modeled result awaits review.

Plan: ../../Tools/SpearAsset/lotus_plan.md. Handoff: ../../Docs/ImperialSpear.md.
Pre-lotus recovery: ../../Saved/Diagnostics/ImperialSpear/PommelLotus/Before/.
Blender MCP used a hidden BelowNormal task-owned process,3 CPU render threads
and sequential bounded stills; the process was closed after final save.
