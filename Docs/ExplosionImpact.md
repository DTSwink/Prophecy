# Explosion impact event

October18,2026: user resumed the event previously paused for ZibraVDB work.
The six-file event delta is installed and verified in the open main editor.
Isolated incremental build4 actions/46.73s passed. Fresh ImpactEvents,
RigImpactEvents and DelayedImpactEvents tests all pass without test warnings/errors,
including the previously unbuilt K2 pin and actual PHAT fixture checks.

Main Live Coding8 compile actions passed285.59s. ProphecyJolt patch_0 and game
patch_1 loaded; reload completed15:44:24UTC (one new class/struct, one changed library,
36 unchanged classes). Linker .voltbl diagnostics and duplicate existing test
registration warnings occurred; reload and subsequent verification succeeded.
Editor6904 never restarted. **Base DLLs require a minimal normal build before the
next cold launch**, including this extension and the preceding fragment toggle.

Native reflection confirms binding function, receiver and payload. New Python
wrappers are unavailable after Live Coding; use native reflection/call_method where
possible until the next normal launch. Main owned Play smoke creates the receiver
on the actual placed agent, outside ordinary hit events, and applies force to26
bodies. It does not claim a Python callback timing test: the three isolated native
tests provide callback/cooldown verification. The initial fixture expected a player
agent; this map uses DefaultPawn, so the callback was corrected to select its placed
agent within the same owned session. Play ended normally. Existing map Blueprint
reported its pre-existing missing tagged-actor array warning during BeginPlay.
A_Bomb and PoseAgent compile successfully; reflection status3/native_properties0/
pin_types0/wiring_preserved1. Sampled saved package hashes match pre-load.
The user's A_Bomb now resolves to /Game/_mygame/bomb/A_Bomb; the old path in the
hash receipt is its redirector, not an audit of the moved Blueprint's contents.
No saves or wiring edits. Map is dirty at completion and is deliberately left alone.

## Blueprint use

Call **Bind Explosion Impact** from the agent's BeginPlay, with **Agent = Self**.
Drag from **Event** to create a matching custom event. Its Impact struct exposes
Explosion Origin, Impact Location (affected body's COM), Hit Component, Bone Name,
and actual applied Impulse in kg cm/s. This is the first delivered body's impulse,
not a sum over the character. Alternatively add one Explosion Receiver component
and bind its On Explosion Impact dispatcher. Repeated identical binding is idempotent.
No existing Blueprint graph is rewired automatically.

The first actual explosion impulse fires immediately. Every limb and explosion
shares the actor's0.5 authored second (30 unpaused game ticks) cooldown. Ignored
notifications never extend it and never suppress the physical push. The first hit
at/after the deadline fires again. Actors have independent gates. Ordinary collisions
do not emit this event; Generate Physical Hit Events can stay disabled.

Travelling explosions emit on actual arrival, not scheduling. Deleted, replaced,
static, kinematic or radial-impulse-disabled bodies do not emit. The existing wave
simulation-time arrival clock remains unchanged; notification cooldown follows the
project's game-tick timing convention.

## Implementation and reload safety

New narrow receiver class owns the30-tick gate. No permanent component tick or
per-limb timer. Its world callback unregisters at expiry/destruction. Delivery
collects payloads during the existing body traversal, then executes Blueprint after
body locks, activation and wave queue updates. Gates are reserved before callbacks;
handlers can remove bodies or trigger another explosion without lock reentrancy.

The base explosion scheduler was already installed by the bomb feature. This delta
changes no retained world/scheduler/Agent layout: receiver objects are a new class,
notifications are stack-local, world public header is byte-equivalent. Therefore
Live Coding is appropriate; the older isolated note requiring restart applied to
installing the entire base scheduler, not this extension. No Agent header edit.

Main evidence: Saved/Diagnostics/ExplosionImpact retains installed.patch,
source-manifest.json, preload.json, final/test receipts and remote scripts.
October19 cleanup moved redundant before-source copies and build logs to Recycle Bin.
The isolated checkout is removed; detailed explosion research/performance records
and test summaries remain in C:/Users/singerie/.codex/artifacts/prophecy-explosion-2026-10-18.
Existing performance measurements predate event delivery;
no new event-overhead benchmark claim is made.
