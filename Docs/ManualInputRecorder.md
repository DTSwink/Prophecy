# Manual pose agent input recorder

Only `BP_ProphecyManualPoseAgent` has these variables and the `Initialize Input Recording` function. Call that function once from your BeginPlay; it is deliberately **not wired automatically**. Repeated initialization does not create another recorder. The controls are instance-editable and accessible with ordinary Blueprint Get/Set nodes.

- `Recording Input`: starting recording replaces the selected slot with a new sequence. Turning it off saves that sequence. Ending PIE also saves an active recording. Changing slots while recording saves the old slot and starts the new one.
- `Playing Input`: plays the selected slot, one saved sample per actor tick. Changing slots restarts playback at the first sample of the new slot. After the last sample, this Boolean turns off on the next tick and live input resumes. Playback does not loop automatically.
- `Recording Slot`: nonnegative slot number. Files persist across PIE sessions in `Saved/DebugInputRecordings/Slot_<number>.input`. Slots are shared by manual agent instances so the same recording can drive another instance. Avoid recording multiple instances into the same slot simultaneously.
- `Replayed Input`: current input structure, updated before the pawn's Blueprint Tick. It contains A–Z, digits, common keyboard modifiers/navigation keys, all standard Unreal gamepad buttons (including stick directions), sticks, triggers, special-left touchpad axes, and motion values. With neither recording nor playing enabled, it contains live input from the pawn's player controller, falling back to local player 0 for an unpossessed manual agent.

Connect the structure to your own gameplay functions. Playback provides values; it does not synthesize engine key events or call gameplay functions. Tick order follows controller input → recorder → pawn Tick. There is no real-time resampling: playback at a different tick rate still advances exactly one recorded sample per actor tick. Initialize after setting any custom actor tick interval; the recorder copies that interval.

Recording takes priority if both Booleans are enabled and clears `Playing Input`. Missing/empty/invalid slots turn playback off and return live input. Negative slot numbers are rejected. A recording stops and saves at one million ticks to bound debug memory. Data is buffered while recording, then written through a temporary file; an interrupted recording before its save is not recovered.

No recorder component, Tick, input polling, or recording allocation exists before initialization. Core agent classes contain no recorder fields or hooks. The opted-in manual debug instance necessarily polls live input even when both modes are off, as requested. Recording storage uses 144 bytes per sample on disk; runtime buffers retain the reflected structure.

Validation on 2026-09-15: packed codec round-trip and truncation test passed. In actual `testNN` PIE, initialization was absent by default and idempotent when called; seven full-channel synthetic input frames replayed exactly; EOF resumed live input; six live samples were recorded and replayed tick-for-tick; a new recording replaced an existing slot. Evidence: `Saved/Diagnostics/InputRecorderPIE.json`. Test slots were removed. Initialization remains unwired. The manual Blueprint was backed up under `Saved/Diagnostics/InputRecorderBackup` before editing.

Installed in the successful normal Editor build on 2026-09-16; Unreal reopened on `testNN`. The Blueprint initialization remains unwired as requested.
