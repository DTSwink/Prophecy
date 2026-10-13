# Rigid holster and restored-lab parity — October 12

User requested incremental Unreal parity against the restored lab, with questions
raised before further behavioral decisions. Lab motion code must not be changed
without telling the user. The only authorized lab edit in this pass is copying
the user's revised holster placement from Unreal.

## Rigid mount

Follow-up: user deleted the obsolete holster constraint and chose to test the
current motion before further parity changes. Runtime D/S and reset do not
require that component; the temporary hand/sword grip is separate. The editor
mount helper now accepts its absence and only clears legacy endpoints when
present. This editor-only source adjustment awaits the next build; no compile,
restart, Blueprint edit or Play interruption was needed for the deletion.

The editor's placed holsters showed a pelvis socket, but the Blueprint SCS did
not save that socket. Fresh PIE holsters attached to PhysicalMesh without a
socket. The old holster-to-PhysicalMesh/pelvis motor constraint still had both
endpoints and exerted large forces even though holster simulation/collision were
off. Breaking it after the first captured tick was too late to fix admission.

Explicit editor command `Prophecy.Editor.MountRigidHolster` saves the pelvis
socket and converts the user's current world placement into pelvis-local space.
It clears both endpoints of the old `PhysicsConstraint`; its component, motor
settings and all other Blueprint wiring are retained. Placed-instance transform
overrides must be updated after Blueprint reconstruction as well as its template.
The command refuses Play and inconsistent placements across current agents.

Owned first-20-tick simulation captures, three agents:

- Before: pelvis-to-spine01 distance reached 52.62044 cm.
- After: maximum 7.07529 cm, starting at 6.77953 cm; old motor force zero.
- All holsters keep socket `pelvis`; local translation variation <6.3e-14 cm.
- Blueprint graph is byte-identical. PoseAgent BP saved; previously dirty TestNN
  remains open/unsaved. No editor restart.

`Labs/SwordHolsterLab/data/unreal-setup.json` changes only `holster`. Its current
translation is [-29.5059565584,-19.5009341978,-22.5262319661] cm, quaternion XYZW
[-.05204310725,.65858821389,.33673302377,.67094258339]. Scale is unchanged. Current
lab holster stabilization is already zero. User settings are not edited.

## Native behavior reconciliation

- Remove the port-time whole-arm plane transport and shared reference speed
  budget, following the restored `e0da908c` lab rules. Existing numeric pole
  preference speed bound remains.
- For a rigid physical-pelvis socket child, use its exact local mount with the
  current authored pelvis when predicting targets. Do not derive the mount from
  completed physical holster and previous NN pelvis poses. Dynamic holsters keep
  the pre-existing prediction path.
- No other lab motion change, new smoothing, altered tolerance or new knob.

The restored lab reproduces a 124.59-degree arm change in one historical captured
near-straight-arm case. The old no-flip assertion must not be described as passing
after this rollback. This is separate from the first-tick rig explosion fixed
above. Earlier port receipts are historical, not validation of the restored lab.

## Verification and next issue

Layout-safe Live Coding compiles/reloads succeeded (118.11s editor repair,
536.87s native reconciliation/editor correction under memory pressure,86.38s
slide-entry reference capture). Editor remains open; normal DLL remains stale.

Native body/pole/entry-inertia primitives match the restored lab below .000005deg
and .000001cm. All six recorded reach/slide-entry timings now match exactly:
idle D27/S56, walk D30/S57, run D22/S43; slides D19/S31 ticks. This is not a
whole-motion parity pass. The aggregate authored test remains failed because its
historical no-flip condition conflicts with the restored reference; no test was
weakened or reclassified as passing.

Walking captures in kinematic and simulation each complete S and D on three
agents. The current user graph now requests D/S at tick15 modulo60 based on
GetHeldSword validity; it is preserved. The old probe's manual tick380 draw is
therefore preceded by the user's tick375 request. These are lifecycle captures,
not an exact manually isolated timing comparison. Holster local transform remains
constant over543 sampled ticks per mode: <1.7e-13cm, <.000005deg.

Found/fixed one additional native timing discrepancy: sword-relative pole capture
occurred on the first sliding update instead of at the transfer boundary. Calling
the existing no-advance pole operation in StartSlide now captures that frame
without adding time/state or altering the lab. Running-D sliding pose discrepancy
falls from about4.4deg to below.03deg before early return.

Remaining largest recorded discrepancy is running-D release/return: starts at
action tick41, peaks95.94deg at tick47. Native early-return grip reconstruction
does one solve per tick; lab prepares four substeps and computes the outgoing
return derivative from its interpolated guide. The former is a candidate cause,
not yet proven by an isolated intervention. Asked user whether to test matching
four substeps only during this overlap, or let them inspect the current result
first. Do not change the lab to resolve it.

Final patched-runtime smoke capture uses the user's current repeated BP trigger,
without manual start/draw injection: all three simulated walking agents complete
S (ticks158–166) and D (282–285). Postflight: exact original Blueprint graph,
reflection status3/native_properties0/pin_types0; current lab settings hash
unchanged; Play stopped, only previously dirty TestNN remains unsaved.

Raw evidence/backups/scripts: `Saved/Diagnostics/HolsterRigid20261012/`.
