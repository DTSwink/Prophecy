# Offline comparison of packaged repeat runs

`ComparePackagedRuns.py` accepts one or more existing `runner.json` paths. It launches no UE process, runs no build, and changes no runtime setting. It reads the native reports and invokes the current packaged validator directly, then supplements it with exact per-row NN/call/timer/receiver checks. It writes new comparison JSON and Markdown files; it refuses duplicate runner paths and existing output destinations.

PowerShell usage (replace the runner paths with actual R5 reports):

```powershell
& 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' `
  'Saved/JoltMigration/PackagedR5ComparisonDraft/ComparePackagedRuns.py' `
  'ABSOLUTE/PATH/TO/DEVELOPMENT_RUN_A/runner.json' `
  'ABSOLUTE/PATH/TO/DEVELOPMENT_RUN_B/runner.json' `
  'ABSOLUTE/PATH/TO/SHIPPING_RUN_A/runner.json' `
  --output 'Saved/JoltMigration/PackagedR5ComparisonDraft/NEW-COMPARISON.json' `
  --markdown 'Saved/JoltMigration/PackagedR5ComparisonDraft/NEW-COMPARISON.md'
```

The default validator is `Saved/JoltMigration/PackagedNNCrowdDraft/Validate-PackagedNNCrowd.py`; `--validator` can select an explicit retained validator. Its current hash and each runner's recorded validator hash are both captured. A fresh strict validation pass is required for acceptance. The script exits **1** if any run fails; diagnostic timing is still written with failed gates visible. It never weakens historical reports to obtain a pass.

Every original sample is retained in order with source report hash, frame index, cumulative NN counters and deltas, NN timer deltas, complete phase timings/calls, native body/joint counts and coverage counters. Initial/final counters and complete totals remain visible. The original full native report, including every agent-level record, is referenced and hash-checked rather than copied again. The tool checks runner/package/native-result/recorded-validation hashes; it does not replace the separate full staged-file/package provenance audit.

Each run has total, actual-NN-step and interstitial groups. Each group reports mean, conventional median, upper median, p95 using sorted index `floor(0.95*N)`, maximum, minimum and count above 10 ms. NN classification uses actual cumulative counter deltas, not frame parity. Both the one-step/100-feedback relationship and alternating 30/60 Hz cadence are checked. Exactly one PreUpdate/evaluation/finalization per character and the full query/body/bone workload remain required.

The disjoint world partition is manager tick + agent ticks + coordinator + arithmetic world remainder. The separate manager partition is inference + physical resampling + input build excluding resampling + output + store + visual roots + manager remainder. Other child timers remain available but must not be added to their parents. In particular, native wrapper/composition/RefreshBones lie inside coordinator, query publication lies inside RefreshBones, and store includes pose publication.

Run, Walk and Upper runtime/batch fields establish **loaded model identities**, not three per-step inference calls. This walking fixture invokes Walk and Upper while Run is loaded. The tool does not fabricate per-model invocation counts from loaded batch sizes. It retains aggregate actual NN counters and timer boundaries.

Repeat grouping requires matching configuration, executable/snapshot identity and recorded workload/control fields. Command-line differences are also retained; only `PhysicsBenchJson` and `abslog` output destinations are removed from grouping identity. Development and Shipping never share a repeat group. Each group keeps individual-run statistics, range/mean of run means, worst per-run p95/max and explicitly labeled pooled statistics. Unknown external configuration, scheduling and thermals remain outside that equality claim. Pooled figures never replace individual runs or suppress failed gates.

## Verification completed

`HistoricalR4Test.json/.md` analyzes the original unmodified R4 100-agent runner. The tool retains all 360 rows, exact 180/180 NN groups, 36,000 agent records, 792,000 body/query checks, 3,168,000 bone checks and 18,000 feedback samples. Its 9.471366-ms mean is reproduced. It fails the current validator and explicitly records **100 policies with 33 responses** plus **missing callback-restoration evidence**. These are expected historical defects; this is not an R5 acceptance result.

`TestComparison.py` uses that saved analysis plus clearly labeled in-memory synthetic copies to verify aggregation, exact coverage, preserved maximum, median definitions, phase partitions, configuration/binary/factor separation and failure propagation. `ComparisonTests.json` records the result. The synthetic copies are tests only and are never represented as additional runtime measurements.

Fresh R5 Development/Shipping reports have not yet been analyzed by this draft. No mean, median or tail below 10 ms is promised by the tool.
