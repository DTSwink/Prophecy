# Agent keys in the editor debug camera

Press `;` / use `ToggleDebugCamera` as usual. The editor's default debug camera now forwards the original Prophecy Agent's existing Blueprint key events and legacy input actions. Delegates still execute on that original agent, including its existing function/FlipFlop state. No Blueprint rewiring is needed.

The forwarding component is created once on camera activation and destroyed on deactivation or EndPlay. Forwarded bindings do not consume input or block the camera's stack, so matching keys can still operate the free camera. Axis/look bindings are not copied. This targets the current Blueprint key-event setup, not arbitrary Enhanced Input action mappings or dynamically added bindings after camera activation. A deliberately configured custom debug-camera class is preserved.

Installation uses the CheatManager-created delegate, with no Tick, timer or polling. Installation and forwarding code are guarded by `WITH_EDITOR`: packaged Development/Test/Shipping games install no hook and perform no forwarding. The reflected class can exist as metadata in packaged builds but is not selected or instantiated by this feature.

Implementation: `Private/ProphecyDebugCameraController.h`, `Private/ProphecyDebugCameraInput.inl`, module startup/shutdown in `GameAnimationSample3.cpp`. The inline implementation avoids changing unity-file grouping for retained runtime globals. `Prophecy.DebugCamera.InstallInput` installs the editor hook after Live Coding; normal launches install it automatically.

Validated in editor PIE on 2026-09-19: the existing Blueprint Right Shift key dropped the original agent's sword in debug camera, re-entering the camera and pressing it restored the sword through the same FlipFlop, and normal input dropped it again after exit. Evidence: `Saved/Diagnostics/DebugCameraKeys.json`. No Blueprint/map edits or saves; Live Coding succeeded without restart. The check covers actual key delivery and repeated activation, not arbitrary Enhanced Input mappings.
