# Final fight fixture package

Both configurations pass the final fixture group on 10 September 2026:

| Configuration | Authoritative result | Runtime |
|---|---|---|
| Development | `Packages/Development-Resume-20260910-020305-616/result.json` | Exit 0, ensure delta 0 |
| Shipping | `Packages/Shipping-RuntimeResume-20260910-022749-979/result.json` | Exit 0, ensure delta 0 |

Each validates the saved Static testNN floor, all 28 actual A_Sword lifecycle checks, all 10 dropped-sword/floor checks, and both matched 12-step held-sword/fighter contact trials with cleanup. The native opt-in `-JoltFightValidationDir=` entry runs on Entry and inspects testNN without beginning that map's gameplay.

This is a **functional fixture package**. It is not a playable production game, an attack/cutting test, rendering acceptance or a new NN/performance result. No raw NN models are staged; these fixtures disable automatic NN manager creation and publish manual poses. Cutting, rope, noose and boat remain deferred.

## Evidence and recoveries

Development's original UAT build/cook/stage completed successfully in `Packages/Development-20260910-003428-361/`. The outer verifier falsely reported an ACL settings asset missing because PowerShell's `ChangeExtension(relative,$null)` retained a trailing dot. The one-line path fix retained all required runtime closure checks; all 56 external runtime packages were present. `../Resume-FinalFightDevelopment.ps1` verified and ran the existing stage without rebuilding, recooking or restaging.

The Development recovery audit explicitly records a historical limitation: the original wrapper checked Editor hashes in memory but failed before persisting them; full cook/stage hashes were first persisted during recovery. Current complete manifests and preserved original inputs/build logs are evidence, not reconstructed pre-cook hash records.

Shipping's compiled executable/receipt/Jolt DLL were reused by `../Resume-FinalFightShippingStage.ps1`, which explicitly used `-skipbuild -skipcook` with the unchanged shared Development cook and a fresh Shipping stage. Stage/package UAT exits 0 in `Packages/Shipping-StageResume-20260910-021815-430/`.

Client Shipping ignores command-line map selection, so the final runtime uses a fresh external saved Engine.ini via UE's supported `-EngineINI="absolute path"` argument. Its only setting is:

```ini
[/Script/EngineSettings.GameMapsSettings]
GameDefaultMap=/Engine/Maps/Entry.Entry
```

`../Resume-FinalFightShippingRuntime.ps1` reran the same staged executable without UAT, build, cook or stage changes. The exact ini hash is checked before/after runtime. Project defaults still select mybasic. The original failed runtime is preserved; the successful runtime has its own fresh directory and reports. Source support, the original runner and its minimal reviewed variant are in `../ShippingRuntimeRecovery-20260910/`.

All source/assets/Editor binaries, the complete reused cook, staged payload and Shipping executable/DLL identities were checked by the recovery gates. Fresh reports must identify Shipping, non-Editor execution, all three exact fixtures, successful cleanup and exit zero. Ensure counts are recorded separately. Do not weaken these checks or relabel the package as full gameplay acceptance.

## Retained files and future use

The successful Shipping stage is retained at:
`C:/Users/singerie/.codex/tmp/ProphecyJolt/FinalFight-Shipping-StageResume-20260910-021815-430/Stage`.

Its fresh runtime ini and fixture reports are retained at:
`C:/Users/singerie/.codex/tmp/ProphecyJolt/FinalFight-Shipping-RuntimeResume-20260910-022749-979`.

The successful shared Windows cook remains at:
`C:/Users/singerie/.codex/tmp/ProphecyJolt/FinalFight-Development-20260910-003428-361/Cook/Windows`.

The duplicate Development stage was removed only after both configurations passed, with its immutable manifests/reports preserved; see `../RemovedVerifiedDevelopmentStage-20260910.json`. Its runtime cannot be rerun until a new stage is created. The completed Shipping PCH was also removed to recover storage; no further build is needed for this accepted package.

The original `Build-FinalFightPackage.ps1`, `Run-FinalFightPackage.ps1` and recovery helpers are pinned archival recipes for this candidate. Do not blindly rerun them: outputs are immutable, the original Shipping runner needs the explicit saved-config startup layer above, and source/asset changes require a fresh candidate. The latest registry is `FightCookRegistry-20260910-023258.json` (SHA256 `620ADCCCC1D03AF07F3B937BD784975D627535B568C5E57BC3C3DCC11F4655A1`), with 12 roots, 334 runtime Game packages and 56 runtime external packages. Actual cooking includes 2,974 packaged assets through dependencies.

User-facing startup and remaining integration scope: `Docs/JoltFightSetup.md` and `Docs/JoltIntegrationStatus.md`.
