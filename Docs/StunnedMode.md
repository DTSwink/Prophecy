# Stunned state

- **Start Stunned** takes Duration Seconds (default1). It immediately sets
  **Is Stunned** true. Calling it again replaces the remaining duration with a
  full new duration; it does not fire the completion event for the old timer.
- **Disable Stunned** clears the state immediately, without an event.
- **Event Stunned Ended** fires once on natural expiry. Is Stunned is already
  false inside the handler. Starting another stun from the handler is supported.

One second is60 unpaused game-world ticks, independent of FPS and time dilation,
matching the existing duration convention. Positive fractions round up to the
next whole tick. Zero expires immediately and fires the event synchronously.
Negative/nonfinite durations return false and leave the current stun unchanged.

This exposes state and an expiry event for Blueprint gameplay logic; it does not
automatically stop attacks, NN inference, movement or change physical settings.
Agent reset cancels the stun silently. Destruction and world teardown discard it
without firing completion. State defaults off and is runtime-only.

Only stunned agents are registered with one shared world-tick callback. The
callback is removed when the last stun ends; there is no scan of unstunned
agents, extra component or reliance on the actor's own Tick. Expiry dispatch
handles callbacks that restart/cancel other agents safely.
