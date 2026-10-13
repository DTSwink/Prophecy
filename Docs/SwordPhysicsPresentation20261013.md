# Sword mesh/native body synchronization — October13

User authorized fixing the measured visible sword/native collider separation.
The previous 9.044cm/7.482deg discrepancy was in our Unreal–Jolt integration:
the native step used an NN-pelvis prediction, while the post-step equipment path
wrote another mesh pose against the actual holster. Attached kinematic body
publication intentionally retained that independently moved mesh.

## Decisions

- During tip alignment/sliding, the completed native sword body is the source
  of the displayed mesh transform. The holster-local trajectory still drives
  that body; the hand follows through the existing captured joint. No second
  independently positioned visible sword and no new joint, damping or motor knob.
- In Sim, predict the rigidly mounted holster from its actual physical pelvis
  and native linear/angular velocity for the upcoming 1/60 step. Do not replace
  it with the NN pelvis. Kinematic planning remains unchanged.
- Passive holster/hand attachment drives both mesh and kinematic collider.
  Existing transform notifications synchronize it, with a final synchronization
  after runtime scale/ownership changes. Active constrained swords are excluded
  from that feedback path. Fully holstered actors need no feature tick.
- S release seats both representations on the current holster endpoint. D
  release moves both to the existing hand attachment; axial growth updates both.
  Native-body origin offsets are accounted for when publishing the mesh.
- Existing on-demand report now measures mesh/native agreement outside the
  temporary joint phases too. No continuous diagnostic work was added.
- No retained layout changes, Blueprint/lab changes, asset saves or restart.

## Numerical verification

Evidence: `Saved/Diagnostics/SwordPhysicsPresentation20261013/`. `verify.py`
asserts completion, finite errors, correct holster parent during active grip,
mesh/native position <.0001cm and reported rotation <.06deg, active joint present,
and no joint during return/holstered phases.

| Owned Play fixture, all3agents | Completion | Max mesh/body cm | Max reported deg |
|---|---|---:|---:|
| Current moving Sim, two S→D pairs each | All complete,484 sampled ticks | .000004977 | .047718 |
| Current Kinematic, two S→D pairs each | All complete,510 sampled ticks | Native body absent | Native body absent |
| Sim,100% stabilization,.5s return,20% shrink,one pair each | All complete,280 sampled ticks | .000005513 | .049779 |

Kinematic target components match the pre-fix capture **exactly** across19,890
bone samples. Sim joint handle remains unchanged during captured grip; all
alignment durations match their authored tick counts. Current moving Sim tip
error on entering slide is .103–.348cm, reflecting prediction of the physical
parent rather than independently snapping the displayed mesh to an exact path.
The sampled S/D release transform steps were inspected in neighboring ticks;
no additional large ownership discontinuity appeared in those traces.

Dropping during stabilized tip alignment preserves the sword world transform,
destroys the temporary grip, restores exact authored mount and rotation
inheritance, and clears active state. Saved class placement and Blueprint graph
remain unchanged. Postflight verifies TestNN/A_Sword bytes, complete graph, and
lab tuning; dirty user Fab imports were left untouched.

**Remaining limitation:** native hand/sword constraint error is separate from
mesh/collider separation. Current moving cycles peak at1.324cm/4.236deg; the
100%-stabilized fixture peaks at1.677cm/9.239deg. These are not zero and this
patch does not claim all physical hand jitter is solved. The reported tiny
rotation disagreement includes native float/quaternion numerical precision;
no stronger normalized angular-error claim was tested.

Live Coding compilation succeeded329.92s, reload succeeded23:56:18UTC.
Editor13688 remains open outside Play; only owned sessions were ended and the
temporary FPS cap was restored. Normal DLLs remain stale: normal build before
the next cold launch. No push requested/performed.
