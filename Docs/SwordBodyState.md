# Get Physical Body State: held sword

Pass `sword` as Bone Name on the existing Agent node. Ordinary bone queries are unchanged.

While held, returns the sword body world transform, world center-of-mass linear velocity in cm/s, world angular velocity in radians/s, and whether the sword body is independently simulated. Jolt welded swords report native inherited motion including angular velocity crossed with the offset from the carrier COM to the sword COM; their Is Simulating output is false. Independent Jolt/Chaos swords report their own actual body state. Ordinary kinematic swords reuse the controller's existing carried-motion samples, converted from component-origin to COM velocity.

When no sword is held (including after completed drop/hide), Return Value is false, both velocities are zero, World Transform is identity, and Is Simulating is false. A failed native-body read also returns cleared outputs. No additional tick or history collection is installed.
