# UEFN Manny limb colors

**Set Limb Color** takes Agent, Bone Name and Color. RGB sets the tint; alpha is
its strength (1 replaces base color, 0 leaves the original material color).
The operation is per agent and affects both Mesh and PhysicalMesh. Examples:
`head`, `upperarm_r`, `lowerarm_r`, `hand_r`, `thigh_l`, `calf_l`, `foot_l`.
Fingers belong to their hand; toes belong to their foot. Twist/helper bones map
to their nearest listed ancestor during mesh preparation. **Get Limb Color Bones**
returns the accepted names. Unknown names or unsupported materials return false.

**Reset Limb Color** restores one region. Bone Name `None` restores every region,
the original material instances, and removes the per-agent color component.

This is a visual color override, not a physical-material change. Geometry,
skinning, PHAT, dynamics and collision are unaffected. It preserves the original
material's opacity, normal, metallic and roughness behavior. It works with the
project's stock and Masked Bicolor Manny materials, including their instances.

The mesh stores a region lookup in UV channel 2. A 32×1 per-agent palette is
sampled in the vertex shader; color is interpolated over triangles, avoiding
unrelated palette colors along region boundaries. Existing UVs remain intact.
There are no additional mesh sections or draw calls and no CPU tick callback.
Using colors adds the palette lookup/interpolators to the material; changing a
color uploads a 256-byte palette. Agents that never use the node keep their
original material. Repeated identical settings do not upload again.

One-time preparation is `Prophecy.Editor.PrepareLimbColors Audit|Apply`, after
creating the neutral palette. It refuses to overwrite a pre-existing UV channel
2 and leaves assets unsaved for validation. Original asset backup and preparation
records: `Saved/Diagnostics/LimbMaterials20261006/`. The generated materials and
palette live in `/Game/_mygame/Materials/LimbColors`, included in cooking.
