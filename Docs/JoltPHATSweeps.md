# Per-agent attack PHAT sweeps

Predictive sweeps automatically run only during an attack, including pre-Armed preparation. Locomotion, dodge and parry do not enable them. Attack entry captures the existing `Get Attack Bones` selection:

- Punch: striking hand and lowerarm, plus the sword if held in that hand.
- Kick: striking foot and calf.
- Headbutt: head.
- Slash/pike: held sword only. A welded sword selects its compound leaf, not the carrier hand.

Attack completion/cancellation clears the selection; a chained attack replaces it. Missing weapons and empty selections never fall back to the whole body. Other bodies remain ordinary collision partners.

**Set Jolt PHAT Sweeps** takes Agent, Enabled (pin default false), Strength (1), Max Iterations (64). `Enabled=false` opts that agent out, including subsequent attacks. `Enabled=true` restores permission; idle agents still do not sweep. Automatic permission is enabled until explicitly overridden. Call on BeginPlay or state changes, not every Tick. Valid strength is 0–1; iterations 1–128. Invalid input leaves the configuration unchanged; zero strength also disables requests.

**Get Jolt PHAT Sweeps** reports effective attack activation plus saved strength/iterations. It reports inactive outside attacks or without an attack selection. The setter execution pin must be wired.

After the velocity servo, selected native shapes are queried along predicted translation and angular motion against registered collision partners. Object responses, PHAT groups, pair exclusions and welded leaf filtering remain effective. Pairs selected by both agents are processed once, using the maximum strength/iteration setting.

A converged future contact applies equal/opposite normal impulses, weighted by dynamic mass and angular inertia, allowing travel up to predicted contact. Sleeping dynamic partners wake. These preventive impulses **never emit gameplay Hit events**. Ordinary solved contacts emit only when their surface points touch/overlap, allowing 0.001 cm numerical tolerance; positive-gap speculative impulses are also excluded from events. Collision response itself is retained.

Already touching pairs remain the normal solver's responsibility. Exhausted queries do nothing. This supplementary response does not enable Jolt LinearCast CCD, add friction/restitution, teleport bodies, or guarantee no penetration after later forces/joint solving.

When no agent requests sweeps, empty-registry guards skip body enumeration and queries. During attacks, selection is one to three strike parts instead of the whole rig; attack names are resolved once at entry. The enabled pass still enumerates registered bodies and checks filtered/bounded candidate pairs. No new frame-rate benchmark is claimed. Disabling one agent stops its outgoing sweeps; another attacking agent can still sweep against it as a collision partner.

Focused tests: `Prophecy.Jolt.ContactShapes.AttackSweepGate`, `Prophecy.Jolt.ContactShapes.SelectiveSweeps`, and `Prophecy.Jolt.HitEvents.SolvedImpulseAndLifetime` cover lifecycle/opt-out, selection replacement, welded leaf masks, translation/rotation prevention, positive-gap event suppression, resting hits and CCD hits.
