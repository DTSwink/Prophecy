# Per-agent attack PHAT sweeps

**Current user choice (October9):** sweeps enabled, restricted to the held sword during the six slash attacks. This supersedes the October7 disabled choice. Current Blueprint already has Enabled=true, Strength=1, MaxIterations=64; preserve it. No CCD, adaptive substeps or enlarged collision geometry added.

Predictive sweeps run only during slashL/LU/LD/R/RU/RD, including pre-Armed preparation where existing collision rules permit contact. Attack entry and family changes select the held sword once; no per-tick attack-name checks.

- Slash: held sword shape only. A welded sword selects its compound leaf, excluding its carrier hand leaf. Physics still applies the sword's response through the hand because they are welded.
- Punch, kick, headbutt, pike, locomotion and defense: no outgoing sweeps.

Attack completion/cancellation clears the selection; a chained or retargeted attack replaces it. Missing/dropped weapons and empty selections never fall back to the whole body. Other bodies remain ordinary collision partners. Existing object responses, pair exclusions and defense filters decide which contacts are allowed, rather than restricting contacts to only the named victim. `Get Attack Bones` remains unchanged, including hand_r for sword attacks; gameplay hit selection is separate from predictive sweep selection.

**Set Jolt PHAT Sweeps** takes Agent, Enabled (pin default false), Strength (1), Max Iterations (64). `Enabled=false` opts that agent out, including subsequent attacks. `Enabled=true` restores permission; idle agents still do not sweep. Automatic permission is enabled until explicitly overridden. Call on BeginPlay or state changes, not every Tick. Valid strength is 0–1; iterations 1–128. Invalid input leaves the configuration unchanged; zero strength also disables requests.

**Get Jolt PHAT Sweeps** reports effective attack activation plus saved strength/iterations. It reports inactive outside attacks or without an attack selection. The setter execution pin must be wired.

After the velocity servo, selected native shapes are queried along predicted translation and angular motion against registered collision partners. Object responses, PHAT groups, pair exclusions and welded leaf filtering remain effective. Pairs selected by both agents are processed once, using the maximum strength/iteration setting.

A converged future contact applies equal/opposite normal impulses, weighted by dynamic mass and angular inertia, allowing travel up to predicted contact. Sleeping dynamic partners wake. These supplementary sweep impulses **never emit gameplay Hit events**. Ordinary Jolt solver contacts emit Hit when they apply a blocking impulse, including speculative contacts across a small gap. This October8 change keeps gameplay informed when the normal solver stops a punch before touching; it does not enable PHAT sweeps or change physics response.

Already touching pairs remain the normal solver's responsibility. Exhausted queries do nothing. This supplementary response does not enable Jolt LinearCast CCD, add friction/restitution, teleport bodies, or guarantee no penetration after later forces/joint solving.

When no agent requests sweeps, empty-registry guards skip body enumeration and queries. During slashes, selection is only the held sword. The enabled pass still enumerates registered bodies and checks filtered/bounded candidate pairs. No new frame-rate benchmark is claimed. Disabling one agent stops its outgoing sweeps; another slashing agent can still sweep against it as a collision partner.

Focused tests: `Prophecy.Jolt.ContactShapes.AttackSweepGate`, `Prophecy.Jolt.ContactShapes.SelectiveSweeps`, and `Prophecy.Jolt.HitEvents.SolvedImpulseAndLifetime` cover lifecycle/opt-out, selection replacement, welded leaf masks, translation/rotation prevention, solved speculative impulse notification, resting hits and CCD hits.
