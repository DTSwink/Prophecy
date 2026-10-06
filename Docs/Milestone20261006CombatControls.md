# Combat controls recovery milestone — October 6, 2026

Recovery tag: `milestone/2026-10-06-combat-controls` on `codex/standalone-sim`.

Includes all pending project changes since the physics/combat milestone:

- Per-bone and descendant magnetization modes, snapshot integration, feet-threshold
  events and timed stunned mode.
- Selective attacking-part PHAT sweeps and contact-only gameplay hit reporting.
- Sword body-state queries, held-sword punch metadata, and sword-only preparation
  collision changes: external collision stays enabled, owner collision waits for
  Armed; melee retains its previous rules.
- Timed root-balancing suspension, attack counter wrapping/manual increment, and
  the attack-start hand inertia gate using the counter captured before reset.
- UEFN Manny limb colors, prepared mesh and three palette/material assets.
- Saved PoseAgent Blueprint and TestNN map, latest Parry ONNX and provenance,
  original current Dodge/Parry checkpoints, documentation and small test receipts.

The checkpoint archive now contains 17 originals (115,337,720 bytes), verified by
`Tools/Recovery/RestoreNNCheckpoints.py`. Historical checkpoint backups remain.
The snapshot manifest covers all committed files except itself and is verified
with `Tools/Recovery/VerifySnapshot.py HEAD`. Bulk external content, build output,
caches and the unrelated marketplace PDF are not included.

Current code compiled successfully through Live Coding without closing Unreal.
Recent focused native and owned-PIE tests are recorded in `ProjectJournal.md` and
`Saved/Diagnostics/*20261006`. Hand threshold tests cover full/half entry, strict
boundary checks, pre-reset capture and unchanged retriggers. Manual counter tests
cover 9,999 -> 0 -> 1, automatic entry, active-attack preservation and isolation.

**Build the normal Editor DLL before any cold launch or restoration.** Some new
reflected nodes currently exist only in Live Coding patches; those patches and
compiled binaries are not recovery inputs. Restore external content first, then
the tracked assets, build the project and open `/Game/testNN`. Historical diagnostic
and migration scripts are evidence, not a sequence to bulk-run.
