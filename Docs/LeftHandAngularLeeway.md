# Left-hand angular leeway

**Set Left Hand Constraint** now uses **Angle Leeway Degrees** in every mode, including full and half attacks. The existing native pin name remains `MaxBendDegrees`, preserving Blueprint connections. The value is the cone half-angle between the left hand's +X axis and the elbow-to-wrist direction: 0 locks bend, 55 permits 55 degrees, and 180 is unrestricted. A rotation inside the cone is left unchanged; this does not lock axial twist or alter hand position.

Use **Mode = All** to apply the angle to locomotion, attacks, parry and dodge. Previously attacks ignored this input and always used 55 degrees. The current Blueprint's wired All-mode node had zero, locking the wrist outside attacks; its starting value is now 55 degrees.

**Set Left Hand Constraint Attacks** has one checkbox for each of the 16 attack families. Checked uses the configured Attack-mode angle; unchecked bypasses this constraint for that attack. Defaults are all checked. Both full and half attacks use the selection, including family changes during an attack. The selector does not disable parry, dodge or locomotion.

**Set Left Hand Constraint Global Enabled** with Enabled=false bypasses the constraint in every mode. True restores the configured angles and attack choices. Repeated angle setters cannot override the global disable. **Free Rotation** on **Set NN Wrist Freedom** remains an independent bypass: either switch can keep rotation free. Neither changes physical joint settings or removes behavior learned by a checkpoint.

The attack decoder applies the requested angle to the left wrist and writes the same corrected rotation into recurrent state. Other modes retain their existing publication/recovery path and easing when the allowable angle is reduced. No new inference, tick or timer is added. Unselected or globally disabled attacks skip the rotation solve; all-checked selections require no per-agent attack-mask entry. New selection storage is cleared on world cleanup, without changing retained manager/model layouts.

Backups and focused verification artifacts: `Saved/Diagnostics/LeftHandAngle20260930`.

Validation (September30): Live Coding loaded15:09:33UTC. Three focused tests passed15:10:22UTC: AttackWrist.Math, Modes and AllCheckpoints. The native test exercises angles0/20/55/110/180 across all four checkpoints, checks only left-wrist rotation/recurrent outputs change, and verifies disabled/180-degree output is bit-identical. Mode tests cover every attack checkbox, independent other-special limits, global/freedom precedence, restored settings and in-cone rotation preservation. The current Blueprint node was refreshed, changed0→55, compiled (status3), read back and saved with existing execution wiring preserved. No full suite or gameplay rollout.
