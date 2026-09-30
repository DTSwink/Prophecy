# Sword collision toggle

**Set Sword Collision Enabled** (Prophecy > Agent > Sword) takes an Agent and an Enabled checkbox, default true.

- False makes the held blade ignore every collision channel, including external and owner contacts. It also disables the existing kinematic sword-contact path.
- True restores the captured collision responses, subject to normal attack timing: weapon attacks wait for Armed; other attacks wait for Hit.
- The preference survives attack transitions, simulation-mode changes, and future equips. Dropping restores the released sword's original responses; the preference remains on the agent for its next sword.
- Grip, simulation, mass, inertia and momentum are unchanged. This does not remove the sword's inertial load from the arm.

Uses the existing immediate UE/Jolt response update, including welded colliders. Configuration and lifecycle changes are event-driven; no new tick, inference or pose work. Repeated identical setter calls return immediately. Sparse preference state is cleaned up at component EndPlay without changing live component layouts.

Validation: Live Coding loaded September 29 at 12:07:09 UTC; reflected Blueprint node verified. The focused `Prophecy.Jolt.Sword.AttackCollisionPhases` test passed at 12:07:55 UTC, covering manual disable through Armed/Hit/end, restoring during wind-up, repeated calls, subsequent equip, drop and kinematic presentation, including native independent and welded collision filters. No full suite, asset save or Blueprint wiring.
