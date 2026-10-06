# Per-agent attack counter

`Get Attack Counter` is a pure Agent node returning an Integer64.

`Increment Attack Counter` is an executable Agent node: adds one immediately and
returns the new Integer64 count, wrapping 9,999 to 0. It does not start an attack
or modify **Ticks Since Last Attack**. Automatic attack entry still increments
normally, so manually incrementing and then starting a new attack adds twice.

- Starts at 0; first accepted new NN attack is 1.
- Wraps from 9,999 to 0 on the next new attack, then continues at 1. Zero therefore also identifies a wrapped attack; use the active-attack state to distinguish idle.
- Increments once when entering an attack, including full and half attacks and all attack families.
- Failed trigger requests, edits to the ongoing attack (including family/target edits), full/half transitions, Armed/Hit output, and attack end do not increment it.
- Agent resets preserve the count. A newly spawned agent starts at 0. Separate agents have independent sequences.
- Runtime cost: one 64-bit field per agent and one increment at attack entry. Getter is a field read. No tick hook, polling, map, allocation, or history.

For once-per-attack behavior, compare this value with a saved `Last Handled Attack Counter`. If different, save the current value before performing the action. Require an active attack for attack-only effects. When tracking several attackers, keep the saved value separately for each agent reference; counter values are not globally unique.
