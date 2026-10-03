# Packaged Development crash: exact offline PDB resolution

The crash occurs inside the benchmark's self-removing bone-finalization callback, immediately after that callback unregisters itself. This is the post-measurement removal lifecycle control, reached from SaveNNJoltCase/SaveMultiJoltCase. The stack supports the source reviewer's callback-storage lifetime diagnosis; it does not implicate the timed Jolt solver.

The fault address RVA **0x968db91** resolves to `UProphecyPhysicsBenchmarkSubsystem::SaveMultiJoltCase::<lambda_4>::operator()`, snapshot `ProphecyPhysicsBenchmarkMultiJolt.cpp:684`, byte displacement 13 within that line. Line 683 unregisters this callback, then line 684 reads its captured Agents/RemovedIndex and assigns through captured bCallbackDisableSucceeded.

```cpp
Meshes[RemovedIndex]->UnregisterOnBoneTransformsFinalizedDelegate(RemovalCallback);
bCallbackDisableSucceeded = Agents[RemovedIndex]->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic);
```

Source and staged executable SHA256 independently match **6d6e1f3657e17fc85fd15aa869fd41776eb739af98ad413e7d30668907314559**. The matching local PDB SHA256 is **498ca9f167741ddd3fdebdf44a966bc71cb72058207d50c375e9763fdffe5b44**. DbgHelp reports PDB symbols, age 1, PdbUnmatched=false, DbgUnmatched=false, line/global/type information available. DLL base is 0x7ff7cd6c0000. The XML and executable were read offline; the Python process used SymInitialize(invadeProcess=false), with a local-only symbol path and no attachment to any other process.

| Frame | RVA | Symbol | Source line |
|---:|---|---|---|
| 0 | 0x968db91 | `UProphecyPhysicsBenchmarkSubsystem::SaveMultiJoltCase'::`2'::<lambda_4>::operator() | ProphecyPhysicsBenchmarkMultiJolt.cpp:684 |
| 1 | 0x968e57d | TBaseFunctorDelegateInstance<void __cdecl(void),FDefaultDelegateUserPolicy,`UProphecyPhysicsBenchmarkSubsystem::SaveMultiJoltCase'::`2'::<lambda_4> >::ExecuteIfSafe | DelegateInstancesImpl.h:921 |
| 2 | 0x15ce050 | TMulticastDelegate<void __cdecl(void),FDefaultDelegateUserPolicy>::Broadcast | No source line available |
| 3 | 0x78fdc09 | USkeletalMeshComponent::FinalizeBoneTransform | No source line available |
| 4 | 0x82baaa7 | USkeletalMeshComponent::FinalizeAnimationUpdate | No source line available |
| 5 | 0x7917ee1 | USkeletalMeshComponent::PostAnimEvaluation | No source line available |
| 6 | 0x791ab58 | USkeletalMeshComponent::RefreshBoneTransforms | No source line available |
| 7 | 0x95912f9 | UProphecyJoltCharacterComponent::PublishCompletedPose | ProphecyJoltCharacterComponent.cpp:719 |
| 8 | 0x9589cef | UProphecyJoltCharacterComponent::ConsumeCompletedWorldStep | ProphecyJoltCharacterComponent.cpp:813 |
| 9 | 0x95985f8 | UProphecyJoltCharacterWorldSubsystem::StepRegisteredClients | ProphecyJoltCharacterWorldSubsystem.cpp:403 |
| 10 | 0x9597d77 | UProphecyJoltCharacterWorldSubsystem::StepExplicit | ProphecyJoltCharacterWorldSubsystem.cpp:511 |
| 11 | 0x9591e5a | UProphecyJoltCharacterComponent::StepAndPublish | ProphecyJoltCharacterComponent.cpp:750 |
| 12 | 0x969516f | UProphecyPhysicsBenchmarkSubsystem::SaveMultiJoltCase | ProphecyPhysicsBenchmarkMultiJolt.cpp:687 |
| 13 | 0x96a026c | UProphecyPhysicsBenchmarkSubsystem::SaveNNJoltCase | ProphecyPhysicsBenchmarkNNJolt.cpp:352 |
| 14 | 0x967126c | UProphecyPhysicsBenchmarkSubsystem::SaveCase | ProphecyPhysicsBenchmark.cpp:682 |
| 15 | 0x966b432 | UProphecyPhysicsBenchmarkSubsystem::EndTick | ProphecyPhysicsBenchmark.cpp:584 |
| 16 | 0x966bfed | TBaseUObjectMethodDelegateInstance<0,UProphecyPhysicsBenchmarkSubsystem,void __cdecl(UWorld *,enum ELevelTick,float),FDefaultDelegateUserPolicy>::ExecuteIfSafe | DelegateInstancesImpl.h:713 |
| 17 | 0x7e5d8b9 | TMulticastDelegate<void __cdecl(UWorld * __ptr64,enum ELevelTick,float),FDefaultDelegateUserPolicy>::Broadcast | No source line available |
| 18 | 0x7e93697 | UWorld::Tick | No source line available |
| 19 | 0x7bc1c2b | UGameEngine::Tick | No source line available |
| 20 | 0x8d4bdec | FEngineLoop::Tick | No source line available |
| 21 | 0x8d59c1d | GuardedMain | No source line available |
| 22 | 0x8d59d0a | GuardedMainWrapper | No source line available |
| 23 | 0x8d5c91a | LaunchWindowsStartup | No source line available |
| 24 | 0x8d68734 | WinMain | No source line available |
| 25 | 0xefaa4ca | __scrt_common_main_seh | exe_common.inl:288 |
| 26 | 0x17374 | Only exact game image/PDB loaded; no network/system symbol lookup. | No source line available |

UE engine frames have public symbol names but no local source line records in this game PDB; those lines are deliberately not guessed. All 26 recorded game-module frames resolve to actual symbols. KERNEL32 was not loaded because system symbols are unnecessary for this diagnosis.

Artifacts: `SymbolizedStack.json` contains exact symbol/line displacements and all hash/PDB evidence; `SymbolizePackagedCrash.py` reproduces the lookup using System32 dbghelp and the original snapshot PDB. No source, executable, PDB or crash file was modified.
