# Head wobble around absolute tick90

Current Agent4 setup: spines03-05/neck01/head strengths.5/.5, mode0; lower spine
and pelvis strengths1/1. Joint damping100 throughout spine/neck/head; tolerance
10cm/30degrees. Authored head changes under1degree80-90, but physical error reaches
27.62deg at84, overshoots9.397deg at92, then8.108deg on the opposite side at100.

Angular velocity IS read. Before constraints the rule is
`w_new=(1-strength)*w_before+strength*rotation_error/h`. At.5 it retains half
previous spin. For a fixed isolated target this fractional-strength rule is
underdamped; in the live chain linear drives, inherited movement, and contacts
also matter. This is physical recovery ringing, not an NN-authored head shake.

Eight140-tick controls completed with EXACT physical-pose prefixes through the
intervention (all captured bones, all3 agents):

| Control | Head error92 | Head error100 |
|---|---:|---:|
| Original |9.397deg|8.108deg|
| Global mode from80 |8.271deg|6.506deg|
| Contacts/self-collision off from85 |11.919deg|8.338deg|
| Angular strength1 from85 |5.546deg|7.072deg|
| Linear strength1 from85 |9.355deg|8.633deg|
| Both strengths1 from85 |10.186deg|10.346deg|
| Both1 AND contacts off from85 |.546deg|.189deg|
| Joint damping0 from85 |11.217deg|7.596deg|

Local mode changes the response, but the wobble also occurs globally. Contacts
alone do not explain it. Increasing angular strength alone or removing joint
damping is not a demonstrated fix. Joint damping acts on relative rotations,
not coherent world-space chain motion. Full strength without contact recovers
cleanly. A future braking correction must retain the chosen attraction strength
and be tested with contacts. The earlier accepted full-strength local repair did
not validate fractional-strength post-hit recovery.

No production code, Blueprint, saved map, or persistent setting changed. All
owned sessions ended; user's dirty Blueprint preserved. One early angular run
aborted before intervention because GetBoneNames was not Python-exposed; replaced
successfully using known bone names. Receipts and exact comparison:
`Saved/Diagnostics/LocalMagHead90_20261007/`.
