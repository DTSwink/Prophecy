# Lotus pommel rebuild — concept 04

The flat leaf pass was rejected. Restart the pommel surfaces rather than add
decorative curves to that mesh. Preserve the 70 non-pommel source meshes.

## Shape targets

- User's final clarification: the circled MAIN BODY must be a three-dimensional
  flower section with four peaks. The flattened leaf construction is rejected.
- Four radial ribs at±X/±Y. At the belly, both width and depth are about49mm;
  the current diagonal valleys have12.809mm radius. Broad cubic concave
  quarter-panels scoop4.515mm inward from the adjacent peak chord.
- V3 was rejected for weak form and insufficiently defined interiors. The current form
  gives each primary ridge a3.2mm crest,1.75mm chamfer and0.28mm shadow channel.
  Inside each quarter,
  a second closed leaf-shaped border has a narrow flat land, small edge break,
  inclined inner wall and1.1mm recessed floor with a0.22mm raised lip.
  Borders close nearz.018/.101; relief fades over3mm at the tips;
  they are part of the continuous shell. The lobes taper into round collars.
  The body now has65 axial rows and analytic axial shading normals to refine
  the curvature while preserving its physical dimensions and relief depths.
  No flat front/back slabs,
  floating tube borders, zero-width fins or painted substitutes for the shape.
- Integral turned collars with broad lips and narrow recessed separator lands.
  The lower seat has a1.65mm straight annular band with small edge breaks and
  a recessed separator; retain the upper rolled lip.
- Six sweeping lotus petals on a fuller V5 bud with17.6mm maximum radius;
  roughly0.870mm flat lip lands, a0.70mm inner carved bevel,0.67mm outer gutters,
  convex recessed fields,0.60mm seating shoulder and a
  defined button-throat bevel ending in a small rounded terminal button.
  V5 retains the fuller physical form and refines it with31 axial rows,
  20 transverse lanes per petal and0.082mm half-width inner bevel toe fillets.
  The bud extends below the old cap;
  keep the shaft, grip and blade fixed. Derive total length and butt socket
  from the final geometry instead of retaining stale2.2m metadata.
- User steering: retain the existing spearhead gold material and plain-gold
  atlas tile, then darken only the carved interiors. Preserve all four atlas
  files and original roughness, metallic, specular and normal inputs. The only
  shader addition is a presence-gated Base Color multiply by `PommelCavity`
  CORNER/FLOAT_COLOR: linear grayscale RGB0.45 in deepest veins through1 outside,
  alpha1. Color.R >0.01 enables the multiply; a missing source attribute has
  Color.R0 and bypasses it. Blender5.1 missing-attribute alpha is1, so alpha
  must not be used as a presence signal. Verify the actual accepted-head render
  with cavity shading enabled and bypassed, using a fixed seed, before export.
  All70 protected source meshes and their color layers remain unchanged.
  Unmasked export copies receive neutral white. Unreal must import mesh colors
  and use BaseColor texture RGB × VertexColor RGB; GLB must multiply `COLOR_0`
  exactly once. No appearance acceptance is implied by this implementation.

## Execution and inspection

1. Save pre-rebuild source/game and texture recovery copies.
2. Build closed meshes with deliberate cavity topology and custom shading normals.
3. Inspect an isolated end view to prove the four-lobe section, plus front,
   45-degree and oblique views. Reject flattened sections, faceting, overlapping
   collars and shaft breakthrough before final delivery.
4. Inspect final gold, a reference-angle close-up and the full silhouette.
   Read cavity shading under the same gold response rather than replacing the
   original roughness/normal maps. Use bounded3-thread CPU renders in
   the hidden BelowNormal-priority Blender MCP process.
5. Fit simple convex collision, regenerate exports/LODs, read back FBX and GLB
   including cavity vertex colors, verify source/atlas preservation, and update
   current handoff with measured results. Include Cavity_Material_Report.json,
   the passing Protected_Surface_Render_Check.json (visible accepted-head view),
   and Preview_Pommel_Reference.png. Counts and extents come from current reports;
   final validation and user appearance review remain separate steps.
