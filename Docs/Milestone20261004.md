# Accepted attack recovery milestone — October 4, 2026

Recovery tag: `milestone/2026-10-04-attack-recovery` on `codex/standalone-sim`.
The user accepted the current Unreal behavior after the slashLD-only tuning import.

This milestone captures the native FK lab return port, per-attack Hold/Trim vectors,
world angular momentum seeding, per-attack main/bone inertia and easing, inertia
hold/decay, additive spine-angle time, and the latest slashLD profile. Continuous
spring remains a standalone lab experiment. The modifier debug node, pause-readable
text, obsolete upper-recovery cleanup, source tests, scripts, journals, saved
PoseAgent Blueprint and TestNN map are included.

The lab backup now contains the current saved profiles and snapshots through 12.
Its launcher portability edits are retained. Lab slashRU angle time .20 is backed
up as lab state only: Unreal intentionally retains .29 because the last import
was restricted to slashLD. Unreal slashLD is base .37 s, main inertia 1, easing 0,
inertia hold .08; the user's Blueprint Alpha Hold 1 / Trim 0 remains intact.

Existing recovery content remains included: the standalone simulation, curated
authored assets, installed NN exports and all 15 original checkpoint files.
The checkpoint restore verifier passed for all 100,610,789 checkpoint bytes.
See [recovery instructions](Recovery.md) for externally restored bulk assets.
The unrelated local marketplace PDF is not part of this project milestone.

## Validation and rebuild status

- The accepted port previously passed 10 focused tests and independent parity
  against 320 lab variants, including moving runtime sampling.
- The subsequent per-attack Hold/Trim normal build passed all 12 focused tests.
- The final slashLD data-only Live Coding build succeeded and loaded at
  20:12:15 UTC. Repeated live returns report the requested .37/1/0/.08 values.
  All other 15 native profile rows and canonical idle data are byte-identical to
  their pre-import versions. No new algorithm change was made for this milestone.
- Editor checkpoint found no dirty content or map packages and no active Play.
- The recovery manifest is refreshed for the staged milestone tree and verified
  against the commit before pushing. Its legacy filename is retained for the
  existing restore command.

The latest slashLD profile is loaded in the current editor through Live Coding.
**Build the normal Development Editor DLL while Unreal is closed before the next
cold launch.** The existing normal DLL predates that data-only change. Compiled
binaries and Live Coding patches are not recovery artifacts. No custom launcher
is needed. The documented restore procedure already builds before opening TestNN.

Small diagnostic scripts and receipts are retained under their original
`Saved/Diagnostics` paths; large frame dumps, editor logs and caches remain local.
Archived scripts are evidence, not instructions to run every repair in sequence.
