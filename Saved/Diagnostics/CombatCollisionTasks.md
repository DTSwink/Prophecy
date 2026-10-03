# Current request — 2026-09-17

- [x] Hook/head intermittent penetration: attempt capture in current setup; research official Jolt non-CCD options even if not reproduced. Prefer optional quality controls over permanent cost. Distinguish missed contacts, physical penetration, and missing notifications.
- [x] Attack -> locomotion: reset registered magic cube at relocated root (zero feedback delta), not merely shift its old error. Cover defense return/cancel/interruption where shared.
- [x] Sword/cube jump around frame 90: temporary PIE only, possessed agent Bool 1 debug false, X=500. Capture sword/hand/root/cube motion and diagnose; research mitigation without CCD.
- [x] Root-speed auto run checkpoint threshold, per agent, Blueprint node, default 100000 cm/s. Keep existing blending and low-speed walk logic coherent.
- [x] Minimal focused validation, journal + concise findings. Preserve authoring state; no CCD toggles or performance bench unless needed/requested.

Related interrupted investigation: mesh hit events. Authored agent notifications false; only SetGeneratePhysicalHitEvents node found in launch ball debug, self=true. First disposable observer failed (Python delegate expected5args, got6), cleaned up own PIE; no runtime evidence yet. Fix observer signature before retry. No source/config fixes made for this investigation.

Completed: see Docs/CombatContactInvestigation20260917.md. Hook phasing/tick90 sword jump not reproduced; documented bounded evidence and official non-CCD research, no speculative production collision fix. Required cube-reset and auto-run code installed/tested.
