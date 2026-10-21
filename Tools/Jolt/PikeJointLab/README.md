# Pike joint comparison

Small standalone fixture linking the project's pinned Jolt 5.6 Development DLL.
It never accesses Unreal or edits assets. CMake imports the installed dependency;
it does not rebuild or replace Jolt. Configure with the installed VS2022 CMake:

```
cmake -S Tools/Jolt/PikeJointLab -B Intermediate/PikeJointLab -G "Visual Studio 17 2022" -A x64 -T "v143,host=x64,version=14.44.35207"
cmake --build Intermediate/PikeJointLab --config Release
Intermediate/PikeJointLab/Release/PikeJointLab.exe
Intermediate/PikeJointLab/Release/PikeJointLab.exe --stress
```

Compares stock SixDOF, stock Slider, coupled five-row pike solve, and stock SixDOF
with full positional correction. Masses 2/10/50 kg, offsets 10/60 cm, with and
without a wall. Wall cases continuously push the connected arm toward the wall;
only the sword/arm pair is collision-suppressed. Stress adds initial 15 rad/s sword
and -3 rad/s arm angular velocity. Each case runs 120 fixed 60 Hz steps at default
Jolt iteration counts. Output gives peak/RMS transverse error, angular error,
maximum sword COM X, contact count and whole-world update microseconds. Timing
is illustrative, not an Unreal FPS benchmark. Stock Slider alone was insufficient.
Full positional correction also helps SixDOF, but the coupled solve removes the
rotation/translation coupling residual in the long-blade spin case.

`CoupledPike.h` includes the exact production `ProphecyJoltPikeJoint.h`; no copied
solver implementation. `HardSix.h` is a comparison fixture only. Actual map
comparison uses `Tools/SwordHolster/ProbeCoupledPike.py --solver off|coupled`,
which owns a short Play session, changes only transient joint opt-in, captures,
and ends its own Play. It refuses an existing user Play. Analyze with
`AnalyzeCoupledPike.py`. Results live in `Saved/Diagnostics/CoupledPike`.

The block contains the two transverse point-on-line rows and three angular rows
in one `J M^-1 J^T` matrix. It factors once during velocity setup, reuses the
factor for all velocity iterations, and recomputes during normal position
iterations. Axial limit and motor stay in stock SixDOF. Full hard-connector
position correction occurs within the island solver, before contact correction;
there is no body pose write after Step. Contacts can leave a small residual.
This is not a guarantee of zero error for arbitrary loads or collision geometry.

October21: `SlashJointLab` includes the exact production `ProphecyJoltSlashJoint.h`.
Build with `--target SlashJointLab` and run the executable in the same Release
directory. It compares stock and coupled slash constraints for1/100 blades,
static/dynamic victims, and verifies the blade plane, locked swings and free
twist. Output includes complete physics-step microseconds, not Unreal FPS.
The three-row slash block retains normal Y/Z limits/motors. Hard blade limits
now use full position correction within the existing solver iterations (pikes
as well); there is no extra world step or global iteration change.

References:
- [Jolt 5.6 slider](https://jrouwe.github.io/JoltPhysicsDocs/5.6.0/class_slider_constraint.html)
- [Constraint derivations, section 2.3](https://danielchappuis.ch/download/ConstraintsDerivationRigidBody3D.pdf)
- Pinned source: `Intermediate/JoltMigration/Upstream/Jolt/Physics/Constraints/SliderConstraint.cpp`,
  `SixDOFConstraint.cpp`, and `PhysicsSystem.cpp` position-solve order.
