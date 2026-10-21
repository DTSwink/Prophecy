# Agent keys in the editor debug camera

## ZQSD flying camera — October21, loaded

User requested ZQSD for the camera during Play. `FlyCam_MoveFB`/`MoveLR` in
DefaultInput.ini now use Z/Q. The current explosionVFX map uses native
DefaultPawn, whose engine-defined axis bindings ignore those project names.
The existing editor startup helper now remaps only DefaultPawn_MoveForward W->Z,
DefaultPawn_MoveRight A->Q, and DefaultPawn_MoveUp Q->A. S/D, mouse, arrow/gamepad
bindings and C/Ctrl/Space/E stay intact. No input events on gameplay actors are
rewired. Engine exposes a const view but no remove/rebind API for its mutable
mapping array; the scoped adapter changes only those three known entries.

Startup installs a PostPIEStarted hook (default bindings are initialized lazily)
and applies immediately when bindings already exist. No tick/polling, no new
native object layout. `Tools/SetPlayCameraZQSD.py` updates loaded project input
settings and runs existing `Prophecy.DebugCamera.InstallInput`; check log for
`ZQSD=1 QDescends=0`. This also serves future Live Coding installs. Normal launch
uses module Startup automatically after a normal build. Both native hook and
existing agent key-forwarding installation are editor-only.

The shared Live Coding build subsequently succeeded. Installed at09:06UTC using
Tools/SetPlayCameraZQSD.py; log confirmed changed=3 ZQSD=1 QDescends=0. Loaded
FlyCam bindings also verified Z/S and Q/D. Python FKey values use import_text
and export_text comparisons. No Play started/stopped, asset saves or restart;
user retains motion testing. Normal DLLs remain stale and need a normal build
before future cold launch.

Press `;` / use `ToggleDebugCamera` as usual. The editor's default debug camera now forwards the original Prophecy Agent's existing Blueprint key events and legacy input actions. Delegates still execute on that original agent, including its existing function/FlipFlop state. No Blueprint rewiring is needed.

The forwarding component is created once on camera activation and destroyed on deactivation or EndPlay. Forwarded bindings do not consume input or block the camera's stack, so matching keys can still operate the free camera. Axis/look bindings are not copied. This targets the current Blueprint key-event setup, not arbitrary Enhanced Input action mappings or dynamically added bindings after camera activation. A deliberately configured custom debug-camera class is preserved.

Installation uses the CheatManager-created delegate, with no Tick, timer or polling. Installation and forwarding code are guarded by `WITH_EDITOR`: packaged Development/Test/Shipping games install no hook and perform no forwarding. The reflected class can exist as metadata in packaged builds but is not selected or instantiated by this feature.

Implementation: `Private/ProphecyDebugCameraController.h`, `Private/ProphecyDebugCameraInput.inl`, module startup/shutdown in `GameAnimationSample3.cpp`. The inline implementation avoids changing unity-file grouping for retained runtime globals. `Prophecy.DebugCamera.InstallInput` installs the editor hook after Live Coding; normal launches install it automatically.

Validated in editor PIE on 2026-09-19: the existing Blueprint Right Shift key dropped the original agent's sword in debug camera, re-entering the camera and pressing it restored the sword through the same FlipFlop, and normal input dropped it again after exit. Evidence: `Saved/Diagnostics/DebugCameraKeys.json`. No Blueprint/map edits or saves; Live Coding succeeded without restart. The check covers actual key delivery and repeated activation, not arbitrary Enhanced Input mappings.
