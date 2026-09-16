# Independent root magic velocities

The original nodes control set 1. The second independent set uses:

- **Set Root Magic Velocity 2**
- **Set Root Magic Ang Velocity 2**
- **Get Root Magic Velocity 2**
- **Get Root Magic Ang Velocity 2**

Both setters retain **Add to Current** (default false). It adds to the selected set only. Each getter reports its own stored set, even while attacks pause application. Setting zero clears only that component of that set; it does not clear the other set or its angular/linear counterpart. Defaults are zero.

Linear velocity is world XYZ in cm/s. Angular velocity is world degrees/s, Z yaw only, as before. The effective additional velocity is set 1 + set 2. Both affect the actual root and full future window through the same existing integration. Full attacks/NN defense pause both; half attacks retain locomotion behavior. Existing self-balancing magic thresholds evaluate the combined additional velocity.

The sum is cached when a setter runs. Root prediction, actual integration, root velocity readback and balancing still consume one existing lookup, with no per-step second lookup or summation. Extra source storage exists only while set 2 is nonzero. Opposing sets can cancel effective motion while retaining their separately readable/editable values. Nonfinite components or sums are rejected without changing either set.

Implementation preserves the existing native velocity-map element layout and uses a separate new map for paired sources, avoiding retained-allocation resizing during Live Coding.
