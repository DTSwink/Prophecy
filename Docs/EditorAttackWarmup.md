# Editor attack warmup and cache

The attack runtime used to create its three CPU model sessions and run startup parity validation synchronously inside the first Trigger NN Attack call of each Play session. A current-scene baseline recorded a696ms frame at the first kick (tick103), versus26/38ms around subsequent attack starts.

`Prophecy.Editor.AttackWarmup 1` is the new editor default. In PIE, the locomotion manager initializes attack models after locomotion initialization and before initializing agents. Startup parity still runs, using disposable seed buffers; it does not trigger an attack or alter any agent history, target, pose, Armed or Hit state.

When Play ends, one successful native model may be retained for the next Play session. It is exclusively moved into a new manager, never shared between active worlds. Only the model, model-data objects and inference scratch storage survive; actor references and per-agent recurrent state do not. The next manager restores batch size1 and runs the existing parity check again. Failed initialization is not cached. One idle entry bounds retained memory; engine pre-exit releases it before runtime module shutdown.

At acquisition, content hashes cover the runtime/native contracts, their referenced network files and present optional headbutt/half-attack data. Same-size or same-timestamp changes invalidate the cache. These reads happen during startup, not on each attack or tick. This is an in-memory editor cache, so restarting Unreal loses it.

Commands:

- `Prophecy.Editor.AttackWarmup 0`: restore lazy attack initialization for new Play sessions.
- `Prophecy.Editor.ClearAttackCache`: release the idle entry and prevent currently leased models from being returned to it. Active attacks keep running.

This code is excluded from non-editor builds. Cold model creation still costs time on the first Play, now before gameplay. This does not promise to remove unrelated shader, asset-loading, defense-model or memory-pressure stalls.

## Validation

Normal Editor build succeeded in60.22s (seven actions). All28 focused tests passed2026-09-24 09:54:51UTC, including the new fingerprint test: same-size/timestamp weight mutation, contract-only changes, restored contents and missing model rejection. Restored pose Blueprint compiles status3 with zero stale native types/pins and no repaired defaults.

Same-binary, same-restored-Blueprint comparisons each captured302 frames:

| Mode | Attack initialization | Largest frame near first attack | Later attack starts |
| --- | ---: | ---: | ---: |
| Warmup disabled | 621.9ms at world time1.717 | 648.0ms | 25.1 /25.6ms |
| Warmup enabled, cold cache | 643.7ms at world time0 | 30.9ms | 27.0 /26.8ms |
| Warmup enabled, reused cache | 15.9ms at world time0 | 28.6ms | 27.7 /33.3ms |

Every captured attack-state sequence matches the control run. Each startup parity check reports the same maximum error1.81794e-6, below the unchanged1e-3 acceptance threshold. This establishes removal of the measured first-attack model-loading stall; it is not a guarantee against unrelated frame spikes (whole-capture maxima55.1/48.0ms in the two enabled runs).

Evidence: `Saved/Diagnostics/AttackStartup-comparison.json`, `AttackStartup-lazy-control.json`, `AttackStartup-prewarm-cold.json`, `AttackStartup-prewarm-reused.json`; scripts `CaptureAttackStartup.py`, `AnalyzeAttackStartup.py`, `TestEditorAttackCache.py`. Default warmup1 restored, owned Play ended, capture references released, Unreal open; no Blueprint graph changes or push.

## Recovery during implementation

The initial fingerprint test supplied an empty scratch buffer to UE's HashFile. Its read loop cannot advance with a zero-sized supplied buffer, blocking the editor. Corrected to a64KiB reusable buffer. The user authorized termination/restart and autosave recovery. Both saved files and11:36 autosave BP/map copies are preserved in `Saved/Diagnostics/AttackCacheRecovery-20260924-1152`. With the editor closed, those autosaves were restored to Content. After reopening the recovered pose Blueprint was verified, compiled and saved. Later unsaved edits were not claimed recovered. The final full build and successful fingerprint test above include this correction.
