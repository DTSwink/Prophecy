# Combat recovery milestone — October 8, 2026

Recovery tag: `milestone/2026-10-08-combat-recovery`, branch `codex/standalone-sim`.

Includes the pending project changes since the October 6 combat-controls milestone:

- Half-attack reach correction, independent kick ghost locomotion inertia, and a run-only ghost kicking leg. Retired kick half-attack behavior and armed-block controls remain removed.
- Separate FK return Values and Inertia Profile nodes. Imported hookR now uses return .28 seconds, easing 0 and main inertia .1. Other attack profiles remain unchanged by this import.
- Add Root Spread Velocity / Ang Velocity, with a default-zero tick-based delay. One total addition is divided across the selected number of ticks; reset cancels the delay and remainder. Original velocity setters retain their delays.
- Compute Catch Up, including the requested direct-pursuit fallback when interception is impossible.
- Delayed physical tolerance setters and held snapshot blends, accepted local magnetization fixes, and the documented removal of the rejected anti-wobble attempts.
- Sword collision phase/cooldown/gap behavior, updated attack-body membership and collision investigations.
- Current PoseAgent Blueprint, NewFunctionLibrary and TestNN map. The recovered NewFunction half-attack branch is saved, with all recorded connections verified and other current graph nodes unchanged.
- Current standalone lab state, project journals, tests and small validation receipts in `Tools/Recovery/Receipts20261008`.

The existing archive of 17 original NN checkpoints (115,337,720 bytes) was verified again. Runtime exports and the existing curated recovery content remain included. Bulk external assets, generated builds/caches, large diagnostic rollouts and the unrelated marketplace PDF are excluded.

Validation includes the successful normal Editor build during recovery, subsequent successful Live Coding builds, clean Blueprint native types and preserved wiring, and passing focused FK separate-setter/lifecycle and root delay/spread tests. Earlier reach/kick/collision validation and its limits are recorded in the journal. This is not a new full-project test-suite or packaged-build claim.

**Rebuild the normal Editor DLL before a cold launch or restoration.** The latest spread Delay pins and hookR .1 import are currently loaded through Live Coding; patches and binaries are not recovery inputs. Follow `Docs/Recovery.md`. Historical repair commands/scripts are evidence, not a sequence to bulk-run.

`Tools/Recovery/Snapshot20261003.json` is the existing manifest path, refreshed for this milestone. `VerifySnapshot.py HEAD` verifies every stored Git blob against it, including checkpoint bytes and authored assets.
