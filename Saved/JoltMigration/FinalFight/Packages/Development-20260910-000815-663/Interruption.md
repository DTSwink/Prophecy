# Incomplete cook

The normal Editor build passed (23.09 seconds) and Development Game build passed (207.40 seconds). Cooking logged the existing `NewFunctionLibrary → Ang Spring` duplicate `__WorldContext` parameter ensure (`UAT.log`, line 498).

After checking UE 5.7.4 commandlet exit handling, Codex intentionally stopped only this run's cook process, PID 19656, because its logged errors prevent clean commandlet success. The actual recorded cook exit is therefore -1 after termination, and UAT exits 25. This is not a naturally completed cook. No package, runtime fixture or Shipping run was produced.

Unreal was reopened on `/Game/testNN` (PID 17560); the Python bridge confirmed no PIE and no dirty maps/content. A narrowly scoped repair of the serialized reserved parameter is being prepared. No library asset was changed in this attempt.

The incomplete cook contains 4,126 files totaling 869,963,409 bytes. Automatic approval review rejected its deletion with “blocked by policy”; the directory remains. Do not retry deletion through another tool or an ancestor directory. Build logs, inputs and `result.json` remain intact.
