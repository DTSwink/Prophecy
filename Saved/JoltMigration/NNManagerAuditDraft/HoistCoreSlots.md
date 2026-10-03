# Local core-slot table hoist

Draft only; no active edits, build or execution. Apply `HoistCoreSlots.apply-patch.txt` to the current manager after the unused lower-pose builder deletion. Baseline `ProphecyNNLocomotionManager.cpp` SHA256: `5F0BE4D36588DB9294959ED6BFA4A8300FC5BD0011D9C715E85E8106478545B5`.

The current `BuildFullPoseTransforms` lambda builds the same25-entry integer table at lines3646–3651 every invocation. The function calls that lambda consecutively for the previous and current state at3787/3793. The table depends only on the manager's `BodyNames` and `UpperCoreBoneNames`, never on previous/current numerical states, walk policy, outputs or agent index. No callback or layout mutation occurs between those calls; slash processing follows both.

The patch moves the identical integer initialization and lookup loop immediately before the lambda definition. The existing `[&]` capture lets both calls read that one stack-local table. It retains `IndexOfByKey`'s first matching body-name behavior and the assignment loop's last duplicate core-name winner. It introduces no cache across calls, pointer lifetime extension, runtime validation change or asset-layout assumption.

All floating-point pose code, parent iteration order, previous/current calls, local-pose construction, slash handling, carrier transforms and publication stay textually unchanged. Only the integer table runs once instead of twice per publication. This does not alter model or presentation cadence, capsules, query bodies, or the number of bones.

No new tests or performance claim. Parent owns the existing complete NN fixture and all pose/feedback/query validation for the next runtime check.
