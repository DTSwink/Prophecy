# Physics and combat recovery milestone — October 6, 2026

Recovery tag: `milestone/2026-10-06-physics-combat` on `codex/standalone-sim`.

This captures the current saved PoseAgent Blueprint and TestNN map before the
new feet-threshold event work. It includes the parent-local/global magnetization
mode, snapshot holds and special-entry slot 1 restoration, elbow-entry continuity
fix, camera handoff work, attack feedback controls, defense timing/parity changes,
updated installed defense networks, and the Dodge/Parry trainer witness packages
under `Exports`. The rejected sword-contact motor is removed.

All tracked project source, scripts, authored recovery assets, existing checkpoint
backups and the lab backup remain included. The unrelated marketplace PDF and
generated build/cache output remain outside this recovery point.

The normal Development Editor DLL was rebuilt successfully after the final local
magnetization correction. Its cold-load verification passed 24 focused tests and
a 1,400-tick local-mode scene replay. Existing snapshot graph nodes have the new
zero-default Hold Out Time pins. The current Blueprint was saved again for this
push. See `ProjectJournal.md` and `Docs/PhysicalProfileSnapshots.md` for behavior
and diagnostic evidence. Compiled binaries are rebuilt on the recovery machine.

The recovery manifest retains its historical filename
`Tools/Recovery/Snapshot20261003.json`; it is refreshed for this commit and verified
against the committed tree before pushing.
