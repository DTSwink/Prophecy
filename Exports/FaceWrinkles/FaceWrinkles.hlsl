// Custom material node: cheap expression wrinkles for MetaHuman-UV heads (Boss first).
// Output type: CMOT Float 3 (tangent-space normal). Plug the head's existing tangent normal into BaseNormal,
// and this node's output into the material's Normal pin (instead of the base normal).
//
// Inputs (exact names):
//   UV            TexCoord[0]
//   BaseNormal    float3 tangent normal already used by the head (normalized, DirectX/UE convention)
//   Detail        Texture Object  T_Face_WrinkleDetail   (sRGB OFF)  RG = stretch layer XY, BA = compress layer XY
//   M0..M3        Texture Objects T_Face_WrinkleMasks_0..3 (sRGB OFF)
//   Blink_L, Blink_R, JawOpen, Effort, Pain, Shout, Anger, Fear, Grin, Dead, LookDown   scalar params (0..1),
//   same names as the morph targets so one animation curve can drive both (curve flagged Morph + Material).
//
// Cost: neutral face = zero texture reads (uniform branch). Expressive = 5 extra reads (1x 1024, 4x 256) + ~30 ALU.
float bl = Blink_L + Dead + 0.7 * LookDown;
float br = Blink_R + Dead + 0.7 * LookDown;
float total = bl + br + JawOpen + Effort + Pain + Shout + Anger + Fear + Grin;
[branch] if (total < 0.001) return BaseNormal;

float4 m0 = M0.Sample(M0Sampler, UV);   // Blink_L.s  Blink_R.s  JawOpen.s  Effort.s
float4 m1 = M1.Sample(M1Sampler, UV);   // Effort.c   Pain.s     Pain.c     Shout.s
float4 m2 = M2.Sample(M2Sampler, UV);   // Shout.c    Anger.s    Anger.c    Fear.s
float4 m3 = M3.Sample(M3Sampler, UV);   // Fear.c     Grin.s     -          -
float ws = saturate(dot(m0, float4(bl, br, JawOpen, Effort)) + m1.y * Pain + m1.w * Shout + m2.y * Anger + m2.w * Fear + m3.y * Grin);
float wc = saturate(m1.x * Effort + m1.z * Pain + m2.x * Shout + m2.z * Anger + m3.x * Fear);

float4 d = Detail.Sample(DetailSampler, UV) * 2 - 1;
float2 ss = -d.xy / max(sqrt(saturate(1 - dot(d.xy, d.xy))), 0.05);   // stretch-layer slopes
float2 sc = -d.zw / max(sqrt(saturate(1 - dot(d.zw, d.zw))), 0.05);   // compress-layer slopes
float2 sb = -BaseNormal.xy / max(BaseNormal.z, 0.05);                 // base slopes
float2 s = sb + ws * ss + wc * sc;                                    // derivative-space add
return normalize(float3(-s, 1));
