# Attack recovery Run boost and Armed block

## Set Attack Recovery Run Pinning Boost

Configure once per agent, or when changing the configuration. Inputs: **Enabled**, **Hold Duration Seconds**, **Blend Duration Seconds**, **Boost** (0..1). The feature starts unconfigured/off; node defaults when executed are Enabled=true, Hold=0, Blend=1, Boost=1.

An attack releasing the lower body into locomotion starts the override immediately: full attack completion, full-to-half transition, or attack cancellation returning to locomotion. Hold the configured boost, then linearly blend toward the **current** value configured by **Set Run Pinning Boost**. Changing that ordinary node changes the destination without overwriting its setting. This changes the higher Run foot pin using the same existing rule; it does not force Run or alter Walk pinning.

**Get Run Pinning Boost** is a pure Blueprint float getter for that current effective boost (0..1), including the recovery hold/blend. Outside recovery it returns the ordinary configured boost, default0. It shares the exact read path used by Run pinning; it adds no timer, state allocation or inference. It reports the boost amount, not either foot's resulting pin or the Run checkpoint mixture.

Pure half attack completion releases only the upper body and neither triggers nor restarts the lower boost. Half-to-full or a new lower-body special cancels the override; the next qualifying lower attack exit starts it again. Parry/dodge exit does not trigger this attack-only option. Configuring/disabling this node cancels any existing override. When called synchronously inside the returning **Lower Special Ended** attack event, it applies the new configuration immediately to that same recovery, including the first call ever. Outside that event it configures the next qualifying exit. Disabled/both-zero still bypass, and a replacement special/reset earlier in the callback cancels its event context.

September27 correction: the setter previously canceled the automatically started recovery and left only its next-exit configuration. Thus a node wired in Lower Special Ended could report0 every time despite Boost=1. The setter now recognizes the active lower attack callback and begins the freshly configured hold/blend immediately. No changes to Blueprint wiring or authored values are needed.

This correction compiled and loaded **September27 12:49:26 UTC**, with no reflected object changes. Current Blueprint audit confirmed Hold0.1/Blend1/Boost1 wired after Set Attack To Locomotion Blend in the lower event. No tests or Play session run for this correction, following the user's preference.

Durations follow the project clock contract: 60 unpaused game ticks per authored second, independent of FPS/dilation. Hold>0 with Blend=0 holds then returns immediately. Both zero or Enabled=false removes the configuration. Only active returns have a tick callback; completion retires the entry/callback even if Run is never evaluated. Initial-agent reset restores configuration and cancels transient progress. EndPlay removes configuration, progress and reset state.

## Set Attack Armed Blocked

Call with **Blocked=true** before the checkpoint reaches Armed (before attack entry is simplest). The per-agent setting persists across attacks until set false. It covers both full and half attacks and remains independent of the user's mode/distance Blueprint logic.

The block affects only the transition into Armed, including recurrent feedback. Hit retains its original rule: it requires Armed on a preceding step, or an already latched Hit. Thus a blocked wind-up cannot newly Hit, but an already Armed attack can Hit normally even if the block is subsequently enabled. Pose inference continues with the existing phase. The block also covers the legacy checkpoint's Hit-request-to-Armed shortcut. Raw neural requests remain available in diagnostics. No extra inference, sampling, timer or pose storage is added; the empty sparse set bypasses per-agent lookup.

Set **Blocked=false** when ready. The checkpoint may then arm naturally on its next inference step; this does not force an immediate Armed or Hit. A late block does not rewind a strike that is already Armed/Hit. Current targets continue to update normally. Initial-agent reset restores the setting; EndPlay removes it.

Example flow: configure the recovery boost during setup; set Armed Blocked=true; start your half attack; update its real target while approaching; set Armed Blocked=false at the desired distance. Switching full/half remains under your Blueprint's control.

## Full attack entry and ticks since last attack

Accepted full attack entry calls all four root-magic setters with zero and Add=false: linear/angular channels1 and2. Half-to-full reacquisition does the same. An explicit full-mode Trigger call while an attack is already full also clears them, without reseeding the checkpoint. Rejected requests and pure half entry do not clear the channels. This is an entry action, not a continuous lock; later Blueprint calls can supply new values.

**Get Ticks Since Last Attack** is a pure Blueprint integer getter (int64), defaulting Agent to Self. Counting starts immediately at BeginPlay and restarts after initial-agent reset. A full attack resets it to0 and holds it there throughout full ownership. Finishing/canceling the full lower attack, including full-to-half, starts it at0; each subsequent unpaused simulation tick adds1. Pure half entry/exit does not reset it, and upper completion does not restart it. FPS, agent dilation and repeated reads do not change the count rate. EndPlay removes it. Actors that predate this BeginPlay hook in a Live Coding session start on their first getter read if not held by a full attack.

Counting shares the existing recovery callback. Full ownership keeps only a marker, with no counter ticking. No extra NN inference or pose work. A running count intentionally continues until the next full entry/reset/removal, as requested; it saturates at the integer maximum.

Startup correction: the original implementation stayed0 until the first full lower release. The user requested immediate counting instead; BeginPlay/reset are now wired to start it. Patch39 compiled and loaded September27 **12:08:01 UTC**; library-default repair38, Blueprint status3, other wiring/values preserved, no explicit save/restart. No tests or Play session run for this correction, as requested. The validation below describes the preceding build's attack-transition behavior.

Focused reproduction: `Tools/NN/AttackControls/TestAttackEntry.py` and `CaptureAttackEntry.py`. The latter performs owned-PIE checks before the authored attack at120: full entry, full-to-half, half retarget, half-to-full, half completion, pure half entry/exit, a second full entry and full completion. It checks all four magic values immediately at transitions and exact tick counts afterward.

September27 entry validation: patch38 loaded **11:13:47 UTC**; **2/2 focused tests passed** at11:14:11 (EntryMagicAndTicks and RecoveryAndArmedGate). Final owned live capture passed48 samples: all four channels cleared at full entry/reacquisition, remained unchanged by pure half/rejected entry, counter stayed0 in full mode and counted exactly1 per subsequent lower-free tick. At full-to-half45 it read0, at50 it read5; reacquisition55 reset0; half end65 preserved5; pure half entry70 preserved10 and end75 preserved15; full entry80 reset0; full completion82 started0; tick87 read5. The first capture's scheduled full completion was preempted by the authored automatic half switch at83; the counter correctly advanced at84, so the final test explicitly stopped the full attack at82. Evidence: `Saved/Diagnostics/AttackControls/entry-magic-ticks*.json`. Owned PIE ended. Live Coding library-default repair changed38 archived CDO references, BP status3, other values/wiring preserved, no explicit asset save/restart.

## Recovery and Armed verification

`Tools/NN/AttackControls/TestAttackControls.py` runs the new recovery/latch test, existing regional ownership test, and existing Run boost test. Coverage includes full-to-half, pure half end, full reacquisition, defense exclusion, 30/60/120 FPS timing, hold-only/zero durations, current normal destination, actual effective Run pin, reset/removal, completed callback retirement, legacy/current phase gates and release.

`Tools/NN/AttackControls/CaptureArmedBlock.py` uses an owned PIE session with the authored scene: blocks at tick95, releases at170, records phase progression through230, and ends its own session. It makes no Blueprint changes.

Passing `half` additionally switches the owned attack to half at121. This second live test also passed: half attack stayed unarmed/not-Hit through170, Armed171 and Hit187 after release. Both owned sessions ended. Evidence is under `Saved/Diagnostics/AttackControls/`.

September27 validation: runtime Live Coding patch37 loaded **10:07:28 UTC**; both reflected nodes callable. **3/3 focused tests passed** at10:07:52. The actual current scene runs SlashL: attack starts120, remains unarmed/not-Hit through170 (attack step26), arms171 after release, and hits187. Its existing Blueprint switches to half when Armed. Live Coding required library-default repair (43 stale defaults); Blueprint compiled status3, with other values/wiring preserved and no explicit asset save. The editor's own autosave ran afterward. Include native/reflected changes in the next normal build before a fresh editor launch.
