# Unreal Migration Notes

These notes describe only the boundary for eventually validating the standalone locomotion contract in Unreal. They are intentionally separate from `DEV_JOURNAL.md`.

## Locomotion Contract To Preserve

- Run the authoritative mover at 30 Hz.
- Gameplay supplies only locomotion mode, root-relative speed-stick direction/amplitude, and world-relative orientation-stick yaw.
- The mover owns root position, root velocity, root yaw, and locomotion response classification. Gameplay code must not bypass it by writing a walking/running root transform.
- Preserve the dataset direction convention `[sin(angle), cos(angle)]`, the full directional speed caps, walk adaptive controller, run split response controller, and shared yaw motor.
- Produce exactly eight future root transforms after every current root. Those roots are the conditioning contract for the accepted frozen walk/run body policies.
- Unreal validation should compare per-tick root position, velocity, yaw, response, and future roots against `tools/check_locomotion_parity.py` traces before visual judgement.

## Unreal Runtime Boundary

- The raylib camera, UI, telemetry server, capture controls, precomputed pose-cycle asset, and debug rewind controller do not migrate into gameplay code.
- `data/locomotion_poses.json` contains draw-pruned authored full-body clips for the standalone viewer; it is not the shipping Unreal inference path.
- Unreal should execute the accepted walk/run policies through its native NN runtime using the same mover-generated eight-root input contract, then apply inferred pose output without giving the policy authority over the gameplay root.
- Keep debug replay optional in development and compile it out for the shipping configuration.
