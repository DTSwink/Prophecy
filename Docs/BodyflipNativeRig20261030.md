# Bodyflip native rig profile — October 30

The standalone lab keeps its approved 25-body, 45 kg profile. Native Bodyflip
installs an explicit per-planner profile from the actual native rig; it does not
rewrite PHAT, user tuning, or standalone defaults.

## Why it is required

`Saved/MimicKitUEFN/source-rig.json` still matches both source asset SHA256 hashes
on disk. That PHAT has 23 bodies / 22 joints, 78.254529595 kg, five spine
capsules, and no physical toe bodies. Its five spines weigh 29.816250324 kg,
versus the lab's 10 kg. Spine04 is limited to 10 degrees on each axis;
spine05 to 5/5/8.97 degrees, versus the lab's 22-degree cones/twist.

With the same idle bone transforms, the two mass models place COM 3.164 cm
apart. A 180-degree rotation around the lab COM consequently moves the native
PHAT COM by 6.319 cm even if every bone tracks perfectly. Sharing poses alone
does not establish physical equivalence.

## Contract

`ProphecyBodyflipRigProfile.cpp` serializes prepared native mass, conditioned
principal inertia, COM, collider primitives, joint connector frames and angular
modes/limits. The physical component retains the pre-Enable description because
its Chaos receiver subsequently becomes QueryOnly. Current constraint profiles
and foot-front trim are refreshed on capture. Unsupported convex body colliders
produce an explicit Bodyflip error, without preventing unrelated native physical
animation from starting.

Kinematic agents have NoCollision. Capture therefore creates a temporary hidden,
non-simulating, ignore-all skeletal component with the same mesh, PHAT and scale,
copies available per-body mass settings and joint profiles/frames, and uses the
same native capture/preparation implementation. The temporary component is
destroyed before capture returns. No source object or asset is edited.
The clone also copies the component physical-material override and slot-0
material fallback before body creation, then each available live body's resolved
physical material before mass capture. This preserves material density when the
source has component/body overrides, including NoCollision with no live bodies.
This is included in the normal build and isolated native verification.

The profile is passed separately from sanitized motion settings, installed in an
isolated native VM before sequence/target construction, and retained through
rebuilds. Physical shape frames and principal mass frames remain separate.
Native foot trim changes shape geometry only, preserving prepared COM/inertia.
The 26 animation bones remain; absent toe rigid bodies contribute no mass.

Shared JS uses the profile in mass/spin, attack momentum, legal-joint projection,
aim interpolation, body contact, shoe corners, palm corners and wrist limits.
Native contact queries use the actual physical primitives, without adding the
standalone renderer's stylized geometry. Native connector positions are honored:
current child anchors are effectively zero, while the spine02 parent anchor
differs from the frozen idle bone translation by about 0.52 cm.

Support IK solves the actual native elbow/knee hinge and connector offsets.
The original geometric bend plane remains in use. When the segment-angle sine
falls below1e-4 (about0.006deg), the native float32 connector offsets make that
cross product ill-conditioned. Only there, the physical hinge axis and captured
limb sign supply the plane. This prevents a shoulder flip at full extension
without widening a limit or changing ordinary bends. The standalone rig retains
its existing IK path.

## Verification

- `verify-native-profile.mjs`: 100 randomized poses; independent native-coordinate
  COM error below 4.45e-16 m, conditioned inertia error below 2.67e-15 kg m²,
  connector error below 2.38e-16 m, angular projection residual below 9.20e-16 rad.
  Independent conversion back into the original native connector frames confirms
  twist/swing bounds within 1.34e-15.
- Imported foot boxes, 2 cm front trim with fixed heel/COM/inertia, wrist legality,
  and unsupported-shape rejection pass.
- Twenty complete pre-change lab outputs (mass, COM, joint projection, body
  geometry, target projection, shoe corners) remain byte-identical with no profile
  and after removing a profile. SHA256:
  `371c735d0b6ef1085ecd8b293a3f6adf717800ac4dbf5219edb7a7766c113cd7`.
- `verify-native-profile-aim.mjs`: final 60 spinning native-profile target
  directions pass, maximum direction-vector error 2.21e-7.
- Earlier `verify-native-profile-flight.mjs` fixture: 148 projected frames across foot push/spin,
  one-hand push and paired-hand push. All three push and rise with finite legal
  poses; joint/connector residuals below 5.58e-16. During hand load/push, final
  projected palm gaps are at most 5.75 mm / 2.59 mm, below the 5 cm contact gate.

Fixture: `Labs/BodyflipLab/fixtures/native-rig.json`, with source asset hashes.
Receipts: `Saved/Diagnostics/BodyflipPort20261030/native-profile-{js,aim}.json`.

The normal native build and final actual-agent tests now pass: kinematic/sim,
Big Throw, Small Throw, one-hand and two-hand pushes. Both palms record solved
floor impulses during the paired push. The final hinge test has7,224 checks and
the spinning hand-release history test has248 checks/73frames, including reverse
seeks. See [native results and measured limits](BodyflipNative.md).
This profile does not change native collision exclusions or add self-collision
avoidance. The one-hand physical segment discrepancy passes narrowly at2.954cm
against the unchanged3cm limit.
