from pathlib import Path
import hashlib,json,difflib,datetime
root=Path.cwd(); draft=root/'Saved/JoltMigration/CallbackMeshRestoreDraft'
paths=['Source/GameAnimationSample3/Public/ProphecyJoltCharacterComponent.h','Source/GameAnimationSample3/Private/ProphecyJoltCharacterComponent.cpp','Source/GameAnimationSample3/Private/ProphecyAgentJolt.cpp','Source/GameAnimationSample3/Private/ProphecyAgent.cpp','Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkMultiJolt.cpp']
old={p:(root/p).read_text(encoding='utf-8-sig') for p in paths}; new=dict(old)
def change(p,a,b,count=1):
 assert new[p].count(a)==count,(p,a[:80],new[p].count(a))
 new[p]=new[p].replace(a,b)
h,c,aj,a,b=paths
change(h,'    bool WasEnableCancelled() const { return bEnableCancelled; }','    bool WasEnableCancelled() const { return bEnableCancelled; }\n    // Native ownership is already gone; mesh restoration is finishing at the current publication boundary.\n    bool IsKinematicRestorePending() const { return DeferredMeshRestore || bDisableInProgress; }')
change(h,'    void DisablePhysicalAnimationInternal(bool bCancelEnable);','    void DisablePhysicalAnimationInternal(bool bCancelEnable);\n    void RestoreKinematicMesh(TUniquePtr<FProphecyJoltCharacterState, FProphecyJoltCharacterStateDeleter> RemovedState);')
change(h,'    TWeakObjectPtr<UProphecyJoltCharacterWorldSubsystem> AdmissionCoordinator;','    TUniquePtr<FProphecyJoltCharacterState, FProphecyJoltCharacterStateDeleter> DeferredMeshRestore;\n    bool bPublishingCompletedPose = false;\n    TWeakObjectPtr<UProphecyJoltCharacterWorldSubsystem> AdmissionCoordinator;')
change(c,'#include "Misc/Parse.h"','#include "Misc/Parse.h"\n#include "Misc/ScopeExit.h"')
change(c,'    if (bEnableInProgress || bDisableInProgress)','    if (bEnableInProgress || IsKinematicRestorePending())')
change(c,'    if (!IsInGameThread() || bEnableInProgress || bDisableInProgress)','    if (!IsInGameThread() || bEnableInProgress || IsKinematicRestorePending())')
change(c,'        return Fail(OutError, TEXT("Completed Jolt pose publication lost its bound mesh/AnimInstance or exhausted its revision."));\n    FProphecyJoltCharacterState* const PublishingState = State.Get();','''        return Fail(OutError, TEXT("Completed Jolt pose publication lost its bound mesh/AnimInstance or exhausted its revision."));
    // Refresh(nullptr), TickAnimation and a pending parallel-task completion can run user callbacks.
    // Keep detached cleanup alive until those engine calls have fully returned. No timer or extra tick.
    check(!bPublishingCompletedPose);
    TGuardValue<bool> PublicationGuard(bPublishingCompletedPose, true);
    ON_SCOPE_EXIT
    {
        if (DeferredMeshRestore) RestoreKinematicMesh(MoveTemp(DeferredMeshRestore));
    };
    FProphecyJoltCharacterState* const PublishingState = State.Get();''')
change(c,'''    AProphecyAgent* Agent = RemovedState->Agent.Get();
    USkeletalMeshComponent* Mesh = RemovedState->Mesh.Get();
    if (Agent) RemoveTickPrerequisiteActor(Agent);
    const auto CanRestoreMesh''','''    if (AProphecyAgent* Agent = RemovedState->Agent.Get()) RemoveTickPrerequisiteActor(Agent);
    if (bPublishingCompletedPose)
    {
        // DestroyRig and coordinator removal above are immediate. Changing AnimInstance while its
        // finalizer is still on the stack is forbidden by UE; retain only the cleanup ownership.
        check(!DeferredMeshRestore);
        DeferredMeshRestore = MoveTemp(RemovedState);
        return;
    }
    RestoreKinematicMesh(MoveTemp(RemovedState));
}

void UProphecyJoltCharacterComponent::RestoreKinematicMesh(
    TUniquePtr<FProphecyJoltCharacterState, FProphecyJoltCharacterStateDeleter> RemovedState)
{
    check(IsInGameThread());
    // Keep admission/mode changes barred across every callback from class initialization and refresh.
    TGuardValue<bool> DisableGuard(bDisableInProgress, true);
    AProphecyAgent* Agent = RemovedState->Agent.Get();
    USkeletalMeshComponent* Mesh = RemovedState->Mesh.Get();
    const auto CanRestoreMesh''')
change(c,'''        if (Agent && !Agent->IsActorBeingDestroyed()) Agent->ApplyNNPoseKinematically(0.0f);''','''        if (Agent && !Agent->IsActorBeingDestroyed() && !Agent->ApplyNNPoseKinematically(0.0f))
        {
            LastError = TEXT("Jolt removal could not restore the NN kinematic AnimInstance and pose.");
            UE_LOG(LogProphecyJoltCharacter, Error, TEXT("%s"), *LastError);
        }''')
change(aj,'    if (!IsInGameThread() || !bManualNNPoseApplication || !HasActorBegunPlay()) return false;','    if (!IsInGameThread() || !bManualNNPoseApplication || !HasActorBegunPlay()) return false;\n    if (JoltCharacter && JoltCharacter->IsKinematicRestorePending()) return false;')
change(aj,'    const bool bWasPending = JoltCharacter->IsEnablePending();\n    JoltCharacter->DisablePhysicalAnimation();','''    const bool bWasPending = JoltCharacter->IsEnablePending();
    // The restored NN proxy must observe kinematic mode on its first update, including immediate cleanup.
    if (!bWasPending) SimulationMode = EProphecyAgentSimulationMode::Kinematic;
    JoltCharacter->DisablePhysicalAnimation();''')
change(a,'bool AProphecyAgent::SetSimulationMode(EProphecyAgentSimulationMode NewMode)\n{','''bool AProphecyAgent::SetSimulationMode(EProphecyAgentSimulationMode NewMode)
{
    if (JoltCharacter && JoltCharacter->IsKinematicRestorePending())
    {
        // A finalization callback can request another mode before the detached Jolt mesh is restored.
        // Preserve the accepted kinematic transition until that same call boundary has unwound.
        if (NewMode != EProphecyAgentSimulationMode::Kinematic) return false;
        SimulationMode = EProphecyAgentSimulationMode::Kinematic;
        return true;
    }''')
change(b,'#include "ProphecyNNPoseTypes.h"','#include "ProphecyNNPoseTypes.h"\n#include "ProphecyNNLocomotionAnimInstance.h"')
change(b,'#include "Misc/Parse.h"','#include "Misc/Parse.h"\n#include "Misc/ScopeExit.h"')
change(b,'|| Character->IsComponentTickEnabled() || Agent.GetPoseReferenceMesh() != &Physical || Physical.IsAnySimulatingPhysics())','''|| Character->IsComponentTickEnabled() || Character->IsKinematicRestorePending()
        || Agent.GetPoseReferenceMesh() != &Physical || Physical.IsAnySimulatingPhysics()
        || !Physical.GetAnimInstance() || Physical.GetAnimInstance()->GetClass() != UProphecyNNLocomotionAnimInstance::StaticClass())''')
start=new[b].index('    // Exercise removal from a real animation callback,')
end=new[b].index('    Summary->SetBoolField(TEXT("removed_during_bone_finalization"), true);',start)
new[b]=new[b][:start]+'''    // Exercise real callback removal and a fresh kinematic pose before any later re-enable can repair
    // the class accidentally. The temporary source is isolated from every actual NN publication.
    auto RestoreAudit = MakeShared<FJsonObject>();
    Summary->SetObjectField(TEXT("callback_kinematic_restore"), RestoreAudit);
    RestoreAudit->SetBoolField(TEXT("success"), false);
    const auto ExerciseRemoval = [&]() -> bool
    {
        AProphecyAgent* RemovedAgent = Agents[RemovedIndex];
        USkeletalMeshComponent* RemovedMesh = Meshes[RemovedIndex];
        UProphecyJoltCharacterComponent* RemovedCharacter = Characters[RemovedIndex];
        int32 OriginalPoseId = INDEX_NONE;
        float OriginalInterval = 0.0f;
        bool bOriginalInterpolate = false;
        if (!RemovedAgent->GetNNPoseDataSource(OriginalPoseId, OriginalInterval, bOriginalInterpolate))
        { Error = TEXT("Removal regression requires the original NN source binding."); return false; }
        const int32 ProbePoseId = MIN_int32;
        FProphecyNNPoseSnapshot ExistingProbe;
        if (FProphecyNNPoseStore::GetAgentLocalPose(ProbePoseId, ExistingProbe))
        { Error = TEXT("Removal regression temporary pose ID is occupied."); return false; }
        const FName ProbeBone(TEXT("head"));
        const int32 ProbeBoneIndex = MeshAsset->GetRefSkeleton().FindBoneIndex(ProbeBone);
        const auto BeforeLocal = RemovedMesh->GetBoneSpaceTransformsView();
        if (!BeforeLocal.IsValidIndex(ProbeBoneIndex))
        { Error = TEXT("Removal regression requires the retained head bone."); return false; }
        const FTransform OriginalHead = BeforeLocal[ProbeBoneIndex];
        const TArray<FName> ProbeNames { ProbeBone };
        TArray<FTransform> ProbeLocal { OriginalHead };
        ProbeLocal[0].AddToTranslation(FVector(17.0, 0.0, 0.0));
        FProphecyNNPoseStore::SetAgentLocalPose(ProbePoseId, ProbeNames, ProbeLocal);
        ON_SCOPE_EXIT
        {
            RemovedAgent->ConfigureNNPoseDataSource(OriginalPoseId, OriginalInterval, bOriginalInterpolate);
            if (auto* RestoredAnim = Cast<UProphecyNNLocomotionAnimInstance>(RemovedMesh->GetAnimInstance()))
            {
                RestoredAnim->AgentId = OriginalPoseId;
                RestoredAnim->NNPoseIntervalSeconds = OriginalInterval;
                RestoredAnim->bInterpolateNNPose = bOriginalInterpolate;
                RemovedAgent->ApplyNNPoseKinematically(0.0f);
            }
            FProphecyNNPoseStore::ClearAgentPose(ProbePoseId);
        };
        const uint64 RemovalFrame = GFrameCounter;
        bool bCallbackRan = false, bDisableSucceeded = false, bNativeRemovedInCallback = false;
        bool bClassRetainedInCallback = false, bReentrantModesRefused = false;
        FDelegateHandle Callback = RemovedMesh->RegisterOnBoneTransformsFinalizedDelegate(
            FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateLambda([&]()
            {
                if (bCallbackRan) return;
                bCallbackRan = true;
                // The executing delegate remains bound until the outer refresh and restore return.
                bDisableSucceeded = RemovedAgent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic);
                FProphecyJoltWorldDiagnostics During;
                bNativeRemovedInCallback = !RemovedCharacter->IsJoltPhysical()
                    && !RemovedMesh->IsAnySimulatingPhysics()
                    && Coordinator->GetRegisteredCharacterCount() == RemovedIndex
                    && Owner->GetDiagnostics(During).IsSuccess()
                    && During.BodyCount == uint32(RemovedIndex * Multi::BodiesPerAgent + (Cases[CaseIndex].Floor ? 1 : 0))
                    && During.ConstraintCount == uint32(RemovedIndex * Multi::JointsPerAgent);
                for (const FProphecyJoltBodyHandle& Handle : OldHandles[RemovedIndex])
                {
                    FProphecyJoltBodyState Unused;
                    bNativeRemovedInCallback &= Owner->ReadBody(Handle, Unused).Code == EProphecyJoltWorldResult::InvalidHandle;
                }
                bClassRetainedInCallback = RemovedCharacter->IsKinematicRestorePending()
                    && Cast<UProphecyJoltPoseAnimInstance>(RemovedMesh->GetAnimInstance()) != nullptr;
                bReentrantModesRefused = !RemovedAgent->EnableJoltPhysicalAnimation()
                    && !RemovedAgent->SetSimulationMode(EProphecyAgentSimulationMode::Physical)
                    && !RemovedAgent->SetSimulationMode(EProphecyAgentSimulationMode::HalfSim);
                RemovedAgent->ConfigureNNPoseDataSource(ProbePoseId, OriginalInterval, false);
            }));
        const bool bStepSucceeded = Characters[0]->StepAndPublish(Multi::StepSeconds, Error);
        RemovedMesh->UnregisterOnBoneTransformsFinalizedDelegate(Callback);
        if (!bStepSucceeded || !bCallbackRan || !bDisableSucceeded || !bNativeRemovedInCallback
            || !bClassRetainedInCallback || !bReentrantModesRefused || GFrameCounter != RemovalFrame
            || !Multi::ValidateDisabled(*RemovedAgent, *RemovedMesh, Error))
        { if (Error.IsEmpty()) Error = TEXT("Callback removal did not finish a safe same-frame NN restoration."); return false; }
        const auto FirstLocal = RemovedMesh->GetBoneSpaceTransformsView();
        if (!FirstLocal.IsValidIndex(ProbeBoneIndex) || !FirstLocal[ProbeBoneIndex].Equals(ProbeLocal[0], 1.0e-5))
        { Error = TEXT("Removal returned without consuming the new NN source in its restored AnimInstance."); return false; }
        const double FirstShift = FVector::Distance(FirstLocal[ProbeBoneIndex].GetLocation(), OriginalHead.GetLocation());
        // A second publication in the same engine frame proves the restored proxy continues consuming
        // fresh source revisions rather than merely retaining the completed Jolt pose or a reference pose.
        ProbeLocal[0].AddToTranslation(FVector(7.0, 0.0, 0.0));
        FProphecyNNPoseStore::SetAgentLocalPose(ProbePoseId, ProbeNames, ProbeLocal);
        if (!RemovedAgent->ApplyNNPoseKinematically(0.0f))
        { Error = TEXT("Restored NN AnimInstance rejected its next kinematic pose."); return false; }
        const auto SecondLocal = RemovedMesh->GetBoneSpaceTransformsView();
        if (GFrameCounter != RemovalFrame || !SecondLocal.IsValidIndex(ProbeBoneIndex)
            || !SecondLocal[ProbeBoneIndex].Equals(ProbeLocal[0], 1.0e-5)
            || !Multi::ValidateDisabled(*RemovedAgent, *RemovedMesh, Error))
        { if (Error.IsEmpty()) Error = TEXT("Restored NN AnimInstance retained stale same-frame pose data."); return false; }
        RestoreAudit->SetBoolField(TEXT("success"), true);
        RestoreAudit->SetBoolField(TEXT("same_engine_frame"), true);
        RestoreAudit->SetBoolField(TEXT("native_ownership_removed_inside_callback"), bNativeRemovedInCallback);
        RestoreAudit->SetBoolField(TEXT("class_change_waited_for_callback_return"), bClassRetainedInCallback);
        RestoreAudit->SetBoolField(TEXT("reentrant_modes_refused"), bReentrantModesRefused);
        RestoreAudit->SetStringField(TEXT("restored_anim_class"), RemovedMesh->GetAnimInstance()->GetClass()->GetPathName());
        RestoreAudit->SetStringField(TEXT("probe_bone"), ProbeBone.ToString());
        RestoreAudit->SetNumberField(TEXT("first_local_shift_cm"), FirstShift);
        RestoreAudit->SetNumberField(TEXT("second_local_shift_cm"), FVector::Distance(SecondLocal[ProbeBoneIndex].GetLocation(), OriginalHead.GetLocation()));
        return true;
    };
    if (!ExerciseRemoval()) return Fail(Error);
''' + new[b][end:]
change(c,'''    if (CanRestoreMesh())
    {
        Mesh->HandleExistingParallelEvaluationTask(true, true);''','''    if (CanRestoreMesh())
    {
        // Direct component Disable/OnUnregister also bypasses the Agent wrapper. The guard routes
        // this request through its cached-mode-only path before any restored NN callback can run.
        if (!Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic))
        {
            LastError = TEXT("Jolt cleanup could not restore its Agent's kinematic mode.");
            UE_LOG(LogProphecyJoltCharacter, Error, TEXT("%s"), *LastError);
            return;
        }
        Mesh->HandleExistingParallelEvaluationTask(true, true);''')
change(b,'''    for (int32 AgentIndex = 0; AgentIndex < RemovedIndex; ++AgentIndex)
        if (!Agents[AgentIndex]->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)
            || !Multi::ValidateDisabled(*Agents[AgentIndex], *Meshes[AgentIndex], Error))
            return Fail(Error.IsEmpty() ? TEXT("Failed to disable a surviving crowd member.") : Error);''','''    // Direct component cleanup has no Agent wrapper to update its cached mode. Observe the mode
    // from the restored NN finalizer itself, before DisablePhysicalAnimation returns.
    bool bDirectCleanupSawNN = false, bDirectCleanupModeCorrect = true;
    const FDelegateHandle DirectCleanupCallback = Meshes[0]->RegisterOnBoneTransformsFinalizedDelegate(
        FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateLambda([&]()
        {
            if (Cast<UProphecyNNLocomotionAnimInstance>(Meshes[0]->GetAnimInstance()))
            {
                bDirectCleanupSawNN = true;
                bDirectCleanupModeCorrect &= Agents[0]->GetSimulationMode() == EProphecyAgentSimulationMode::Kinematic;
            }
        }));
    Characters[0]->DisablePhysicalAnimation();
    Meshes[0]->UnregisterOnBoneTransformsFinalizedDelegate(DirectCleanupCallback);
    if (!bDirectCleanupSawNN || !bDirectCleanupModeCorrect
        || !Multi::ValidateDisabled(*Agents[0], *Meshes[0], Error))
        return Fail(Error.IsEmpty() ? TEXT("Direct component cleanup exposed a non-kinematic mode to the restored NN proxy.") : Error);
    RestoreAudit->SetBoolField(TEXT("direct_component_cleanup_kinematic"), true);
    for (int32 AgentIndex = 1; AgentIndex < RemovedIndex; ++AgentIndex)
        if (!Agents[AgentIndex]->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)
            || !Multi::ValidateDisabled(*Agents[AgentIndex], *Meshes[AgentIndex], Error))
            return Fail(Error.IsEmpty() ? TEXT("Failed to disable a surviving crowd member.") : Error);''')
patch=[]; evidence=[]
for p in paths:
 dest=draft/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(new[p],encoding='utf-8',newline='\n')
 patch.extend(difflib.unified_diff(old[p].splitlines(keepends=True),new[p].splitlines(keepends=True),fromfile='a/'+p,tofile='b/'+p))
 evidence.append({'path':p,'active_sha256':hashlib.sha256((root/p).read_bytes()).hexdigest(),'draft_sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
(draft/'Proposed.patch').write_text(''.join(patch),encoding='utf-8')
(draft/'Evidence.json').write_text(json.dumps({'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'DRAFT_NOT_BUILT_OR_RUN','files':evidence},indent=2),encoding='utf-8')
print(json.dumps({'files':len(paths),'patch_lines':len(''.join(patch).splitlines()),'draft':str(draft)}))

