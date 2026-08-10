# Unreal Migration Notes

These notes describe only the boundary for eventually validating the standalone locomotion contract in Unreal. They are intentionally separate from `DEV_JOURNAL.md`.

## Locomotion Contract To Preserve

- Run the authoritative mover at 30 Hz.
- Gameplay supplies only locomotion mode, root-relative speed-stick direction/amplitude, and world-relative orientation-stick yaw.
- The mover owns root position, root velocity, root yaw, and locomotion response classification. Gameplay code must not bypass it by writing a walking/running root transform.
- Preserve the dataset direction convention `[sin(angle), cos(angle)]`, the full directional speed caps, walk adaptive controller, run split response controller, and shared yaw motor.
- Preserve Crawl as a Walk-derived mode with independent speed and root-turn scales, both defaulting to 20 percent. The current behavior supplies zero crawl speed-stick input; future crawl behavior must enter through this same mover contract.
- Crawl is currently attack-disabled but perception-aware. Entering it clears attack/follow/rescue/finishing targets while retaining recognition and the normal footsteps/real-sword-clash sound-investigation head turn. It does not run the automatic empty-target search sweep, promote finishing targets, or sheathe; after a sound check its head returns toward root heading. Unreal must preserve that distinction rather than inferring combat behavior from the crawl animation.
- Produce exactly eight future root transforms after every current root. Those roots are the conditioning contract for the accepted frozen walk/run body policies.
- Unreal validation should compare per-tick root position, velocity, yaw, response, and future roots against `tools/check_locomotion_parity.py` traces before visual judgement.

## Unreal Runtime Boundary

- The raylib camera, UI, telemetry server, capture controls, precomputed pose-cycle asset, and debug rewind controller do not migrate into gameplay code.
- `data/locomotion_poses.json` contains draw-pruned authored full-body clips for the standalone viewer; it is not the shipping Unreal inference path.
- Unreal should execute the accepted walk/run policies through its native NN runtime using the same mover-generated eight-root input contract, then apply inferred pose output without giving the policy authority over the gameplay root.
- Keep debug replay optional in development and compile it out for the shipping configuration.

## Action Validation Contract

- Keep the standalone action sequence ID, action kind, hand use, weapon kind, optional club ID/target, duration, and contact state as the gameplay-side contract. Unreal animation may improve the pose but must not silently change authoritative action completion.
- Autonomous mode commits a validation-required result at contact. Paired mode holds at contact until Unreal returns success or failure for the exact entity ID and action sequence; stale or mismatched responses must be rejected.
- Reach and hold validation may inspect final hand/object separation or any later gameplay constraint. Success commits the action result and failure preserves the previous state; either result completes the action.
- Development replay must record each Unreal validation response with its simulation tick, entity ID, action sequence, and result. Shipping builds may compile replay storage out without changing live action semantics.
- Sword attacks publish attack target, target distance, action progress, and completed-attack count. Unreal may validate the strike at completion, but target acquisition and root movement remain authoritative simulation state. A non-parried completion makes the authoritative deterministic follow-up roll, defaulting to 50 percent; success removes normal cooldown and permits another attack on the next fixed tick. Parry always applies the separate configured parried cooldown and cannot be bypassed by that roll.
- Clubs are persistent gameplay entities. Pickup first completes sword sheathing when needed, then uses the validation-capable timed action; drop remains timed and leaves the same stable club ID in the world. The raylib wood geometry does not migrate.

## Engagement Context Contract

- The deterministic core groups agents by authoritative attack target without per-agent relationship allocations. It derives committed attackers, currently executing attackers, their first four stable entity IDs for inspection, and allies committed to the same primary target.
- Perceived standing-target allocation runs at five hertz, maximizes distinct reachable coverage, balances surplus load, and holds valid assignments for the configured commitment duration. Unreal perception must provide the same active-threat set; it must not replace it with omniscient team state.
- Every mobile standing-target attacker owns one deterministic soft approach sector with configured bearing/radius jitter. Its stable center/side/rear-quarter role is derived relative to the target-to-attacker bearing when the reservation is created. Inside the influence distance, sector tangent, radial pursuit, same-target angular separation, and soft separation from nearby standing allies across other targets become one root-relative speed stick routed through the mover. Outside attack range, sector lateral correction is capped to `0.36` of direct pursuit, keeping intent within about 20 degrees of its target. Unreal must consume that authoritative intent rather than reproducing the raylib geometry.
- Outnumbered steering consumes all active perceived threats, computes their exact smallest bearing arc from its largest circular gap, and centers a 160-degree tactical view direction. Direct pursuit is blended with containment and ally separation through a clamped quadratic/cubic proximity polynomial. The synchronized early-spread option is the influence at normalized proximity `p = 0.3`, defaults to `0.10`, and is bounded to `0.0-0.20`; influence remains zero at the configured sector distance and one at attack range. Same-target attackers consume their complete local group and apply continuous separation below 45 degrees. Exact overlaps use stable entity-ID tie breaking.
- Team counts, engagement anchors, target IDs, and resulting mover stick/orientation intent are gameplay authority. Unreal should provide equivalent transforms and execute the published intent through its mover/NN locomotion path; it must not synchronize the four-ID inspection truncation as behavior state.
- The mint cone, cyan movement arrow, and raylib selected-agent text are debug UI and do not migrate. Collision, attack scheduling, and perception confirmation remain separate systems and are not implied by the steering diagnostics.
- Post-battle finishing remains deterministic gameplay authority. A team-wide standing-opponent tally gates the phase; only non-dead opponents actually seen during the bounded head sweep are promoted into the fixed-size finishing set, and the nearest promoted target is selected first. Unreal must provide equivalent perception/occlusion results but must not infer targets from the raylib `finish` counter, which is debug UI only.

## Head Look Contract

- The standalone core publishes look mode, target entity ID, world horizontal look yaw, and head pitch at the fixed simulation rate. Yaw is limited to `+/-120` degrees relative to the root frame to represent combined head-and-torso turning, pitch remains limited to `+/-80` degrees, roll is always zero, and the shared turn-speed option defaults to 360 degrees per second.
- Outside combat, 0.5 m/s is the exact switch between root-heading and root-velocity look. During Attack behavior, the living combat target's head overrides both.
- The standalone Autonomous approximation derives target height from the accepted reference head and existing grounded-state pose. Unreal should replace that approximation with the confirmed target head-bone transform while retaining the deterministic look mode, limits, and configured turn-rate contract.
- Vision range, horizontal field of view, recognition, retention, and target-acquisition effects are authoritative core state. World occlusion is not implemented yet; Unreal must not infer occlusion from head orientation alone.

## Sound Event Contract

- The standalone core emits deterministic event metadata only; it does not play audio. Locomotion emits on a fixed 0.2-second clock, a real-sword-versus-real-sword parry emits on the first-tick defense decision, and crawl-yell emits exactly when the agent enters Crawling. Any parry involving a club is silent.
- Locomotion reach is `configured maximum * clamp(root speed / 5 m/s, 0, 1)`. Real-sword clash and crawl-yell use the full configured maximum. Event sequence, tick, primary/secondary clash participants, source position, kind, and maximum reach are authoritative replayable state. A clash wakes only nearby Idle listeners into normal look/investigation; vision still establishes recognition.
- Unreal may turn these events into audio and perception stimuli, but the pale-mint raylib ring, its one-meter-per-second debug expansion, fade, and viewer checkbox do not migrate into gameplay code.

## Wound Confirmation Contract

- Defense outcome is chosen on the attack's first simulation tick in both modes. In Autonomous mode, a chosen `hit` lands only at the attack endpoint; the core then cancels an active defender attack without cooldown, applies the deterministic limb wound, and starts that authored attack clip's configured stun when the wound did not enter a more severe incapacitated state.
- Paired mode currently performs none of those landing effects automatically. Unreal/NN must signal whether the exact attack sequence connected and which limb was hit; only an accepted confirmed hit may trigger cancellation, wound, and the attack clip's stun.
- The confirmation input must include simulation tick, attacker ID, defender ID, attack sequence, attack kind, success/failure, and confirmed limb. Stale, mismatched, duplicate, or already-canceled attack confirmations must be rejected, and development replay must record accepted confirmations at their exact tick.
- Unreal confirms contact and limb only. The deterministic gameplay core remains authoritative for attack cancellation, configured per-clip stun duration, melee gain, threshold, decay, injury transitions, attack availability, and weapon dropping. Real-sword hits advance one wound stage; club hits use the melee gauge despite reusing sword animation clips.
- Entering any grounded state releases only hand-held equipment: a drawn sword becomes dropped, a held club returns to world state, and an owned sheathed sword remains equipped. Unreal visuals must follow that authoritative equipment state.
- Attack selection remains gameplay-core authority: a drawn real sword uses the configurable standing-target weapon probability, defaulting to 80 percent sword and 20 percent melee. A living grounded target requires a usable equipped sword, with the existing timed draw first when it is sheathed; its only eligible sword clips are `pike`, `slashRD`, and `slashLD`. If sword use is unavailable, the only eligible melee clips are the authored left/right kicks. Grounded finishing bypasses cooldown retreat/strafe and tactical lateral steering. Unreal supplies animation/contact confirmation in Paired mode but must not independently choose a disallowed attack or movement intent.
