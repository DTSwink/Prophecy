# R6 comparison compatibility draft

The R6 validator reads `args.ort_intra_op_threads`. The original R5 comparator did not supply that field and would reject all R6 comparisons with `AttributeError`. The separately owned `ComparePackagedRuns.py` draft now supplies `runner.get('ortIntraOpThreadsOverride', 0)` and records the requested factor, complete requested tuple, and both full selected-settings captures in its comparison controls. Those fields join the existing configuration/binary/snapshot/runtime-argument grouping keys, so differing selected settings cannot be pooled silently. The comparator also checks that the runner's explicit ORT tuple/argument agrees with its requested factor, and that a nonzero factor is Development-only.

`ComparisonCompatibility.patch` targets `Saved/JoltMigration/PackagedR5ComparisonDraft/ComparePackagedRuns.py`. The baseline hash is `BA953C363305A0344E6205AD089088F2BC44B21EAFC913E61069E728C1656CAA`; draft hash is `20BFAE92512CA138B54ADEDF67CA83E984FD564F01F02D0746A6091C1581B7B7`. The original comparator and exact R5 validator are archived beside the patch. Nothing is promoted by generating these files.

The validator choice remains explicit. Use `--validator Validate-PackagedNNCrowd-R5-ComparisonArchive.py` when reanalyzing an old R5 report after the active validator becomes R6. There is **no automatic fallback** from the R6 validator to the old validator: R6's missing-capture rejection is intentional.

The two offline controls reread the same real R5 run, `Development-C100-20260909-192656-176`:

- `ComparisonR5ArchiveControl.json/.md`: all 20 comparison gates pass with the archived R5 validator. Every one of the original 360 samples and all counters remain unchanged. Missing old-run factor maps to 0; missing old captures remain explicit nulls.
- `ComparisonR6MissingCaptureControl.json/.md`: the draft R6 validator reaches and correctly rejects the missing-before-models capture. This is the sole failed gate. It does not fail with the earlier missing-argument error and does not fabricate R6 provenance for the old run.

`TestComparisonCompatibility.py` checks these results, preservation of all samples and timings, explicit validator argument forwarding, each added grouping key, exact archives, and the unchanged active comparator. Its in-memory grouping mutations are isolated tests, never additional runtime measurements. `ComparisonCompatibilityTests.json` records the checks.

Source review of the three-file ORT patch found no further concrete blocker. UE's enabled `NNERuntimeORT` plugin loads at PreDefault; startup creates the CDO and copies its settings into the environment before the fixture captures it. The two captures read existing native reflection values around `FinishSpawning`, outside timed samples, and compare the typed tuple. The CDO remains configuration provenance, not direct observation of worker execution. The report says so explicitly.

The default UE 5.7 dynamic-layer config parser uses `FParse::Expression`; its balanced-parenthesis handling preserves the runner's full four-field tuple across internal commas. The legacy disabled parser has different comma handling, but a malformed application would fail the new exact raw/typed capture gates. No claim is made that the alternative legacy parser was exercised. Factor 0 adds no `-ini` argument; factors 1/2 add exactly one complete tuple and are refused for Shipping before launch. The strict validator changes add requirements while retaining R5's collision-response, callback restoration, query, body/bone, cadence and lifecycle checks.

This is offline review and tooling validation only. Native compilation, R6 smoke tests and actual thread-factor measurements remain required after root authorizes promotion.
