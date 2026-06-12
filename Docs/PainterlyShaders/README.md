# Painterly Shader Prototypes

This folder contains the painterly prototype code used to generate the selected monkey and UE texture previews.

Selected variants:

| Number | Name | Look |
| --- | --- | --- |
| 06 | `oil_hv_mode_reference_mid` | cleaner oil-paint color islands |
| 11 | `hybrid_flow_oil_chunky_canvas` | chunkier flow-guided oil islands |

Files:

- `painterly_portfolio.py` is the CPU reference baker used for the portfolio images.
- `PainterlyOilShaders.ush` is an Unreal/HLSL include-style port of the two selected looks.

The HLSL is written as a high-quality texture-baking/reference implementation. At the 2K scale used in the previews, the selected radii are large, so use these in a render target bake, an offline material pass, or reduce `RadiusScale` for realtime.

2K preview-equivalent scale:

- 896px monkey reference scale: `1.0`
- 2048px UE texture scale: `2048 / 896 = 2.285714`
- Variant 06 radius: `16 * RadiusScale`
- Variant 11 flow length: `21 * RadiusScale`, oil radius: `20 * RadiusScale`

Example include usage:

```hlsl
// Inputs expected from a material/custom shader context:
// Texture2D Tex;
// SamplerState TexSampler;
// float2 UV;
// float2 TexelSize; // 1 / texture resolution

float RadiusScale = 2.285714; // 2K texture preview scale
float3 oilRefMid = PainterlyOilReferenceMid(Tex, TexSampler, UV, TexelSize, RadiusScale);
float3 hybridChunky = PainterlyHybridFlowOilChunkyCanvas(Tex, TexSampler, UV, TexelSize, RadiusScale);
```

The generated images from the session remain under ignored `Saved/` folders and are intentionally not committed.
