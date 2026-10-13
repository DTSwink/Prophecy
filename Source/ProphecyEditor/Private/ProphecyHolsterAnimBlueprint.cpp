#include "CoreMinimal.h"
#include "Editor.h"
#include "Animation/AnimBlueprint.h"
#include "Animation/AnimBlueprintGeneratedClass.h"
#include "Engine/SkeletalMesh.h"
#include "Factories/AnimBlueprintFactory.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AnimGraphNode_LocalRefPose.h"
#include "AnimGraphNode_LocalToComponentSpace.h"
#include "AnimGraphNode_ComponentToLocalSpace.h"
#include "AnimGraphNode_AnimDynamics.h"
#include "AnimGraphNode_Root.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"
#include "UObject/MetaData.h"
#include "UObject/UnrealType.h"

namespace HolsterAnimBlueprint
{
constexpr TCHAR Path[]=TEXT("/Game/_mygame/assets/holster/Animated/ABP_HolsterStrap");
constexpr TCHAR SharedKey[]=TEXT("HolsterSharedConstraints");
void CopyConstraints(UAnimGraphNode_AnimDynamics* A,int32 Source)
{
    auto& Bodies=A->Node.PhysicsBodyDefinitions;
    if(!Bodies.IsValidIndex(Source))return;
    const auto Settings=Bodies[Source].ConstraintSetup;
    for(auto& Body:Bodies)Body.ConstraintSetup=Settings;
    // The graph node's normal detail callback updates only the edited body.
    // Mirror the whole linked set to its editor preview in one reset.
    if(auto* Preview=A->GetDebuggedAnimNode<FAnimNode_AnimDynamics>()){
        for(auto& Body:Preview->PhysicsBodyDefinitions)Body.ConstraintSetup=Settings;
        Preview->RequestInitialise(ETeleportType::ResetPhysics);
    }
}
void OnChanged(UObject* Object,FPropertyChangedEvent& Event)
{
    auto* A=Cast<UAnimGraphNode_AnimDynamics>(Object);if(!A)return;
    auto* BP=A->GetTypedOuter<UAnimBlueprint>();
    if(!BP||BP->GetPathName()!=FString(Path)+TEXT(".ABP_HolsterStrap")
        ||BP->GetPackage()->GetMetaData().GetValue(BP,SharedKey)!=TEXT("1"))return;
    const int32 Index=Event.GetArrayIndex(TEXT("PhysicsBodyDefinitions"));
    if(!A->Node.PhysicsBodyDefinitions.IsValidIndex(Index))return;
    // Runs inside the Details panel's existing edit transaction, not per tick.
    CopyConstraints(A,Index);
    FBlueprintEditorUtils::MarkBlueprintAsModified(BP);
}
struct FConstraintEditListener
{
    FDelegateHandle Handle=FCoreUObjectDelegates::OnObjectPropertyChanged.AddStatic(&OnChanged);
    ~FConstraintEditListener(){FCoreUObjectDelegates::OnObjectPropertyChanged.Remove(Handle);}
};
static FConstraintEditListener ConstraintEditListener;
template<class T> T* Add(UEdGraph* G,int32 X)
{
    FGraphNodeCreator<T> Creator(*G);auto* N=Creator.CreateNode();N->NodePosX=X;N->NodePosY=0;Creator.Finalize();return N;
}
bool Connect(UEdGraph* G,UEdGraphNode* A,UEdGraphNode* B)
{
    for(auto* Out:A->Pins)if(Out->Direction==EGPD_Output)
        for(auto* In:B->Pins)if(In->Direction==EGPD_Input&&G->GetSchema()->TryCreateConnection(Out,In))return true;
    return false;
}
void Run(const TArray<FString>& Args)
{
    if(!GEditor||GEditor->PlayWorld)return;
    auto* BP=LoadObject<UAnimBlueprint>(nullptr,Path);
    if(!BP&&Args.Contains(TEXT("Create"))){
        auto* Mesh=LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/_mygame/assets/holster/Animated/HolsterStrap"));
        if(!Mesh)return;
        auto* Factory=NewObject<UAnimBlueprintFactory>();
        Factory->TargetSkeleton=Mesh->GetSkeleton();Factory->PreviewSkeletalMesh=Mesh;
        BP=Cast<UAnimBlueprint>(Factory->FactoryCreateNew(UAnimBlueprint::StaticClass(),CreatePackage(Path),TEXT("ABP_HolsterStrap"),RF_Public|RF_Standalone|RF_Transactional,nullptr,GWarn));
        if(!BP)return;
        FAssetRegistryModule::AssetCreated(BP);
        UEdGraph* G=nullptr;for(UEdGraph* Graph:BP->FunctionGraphs)if(Graph->GetFName()==TEXT("AnimGraph"))G=Graph;
        if(!G)return;
        UAnimGraphNode_Root* Root=nullptr;for(UEdGraphNode* N:G->Nodes)if(auto* R=Cast<UAnimGraphNode_Root>(N))Root=R;
        if(!Root)return;
        Root->NodePosX=700;Root->NodePosY=0;
        auto* Ref=Add<UAnimGraphNode_LocalRefPose>(G,-700);
        auto* ToComponent=Add<UAnimGraphNode_LocalToComponentSpace>(G,-450);
        auto* Dynamics=Add<UAnimGraphNode_AnimDynamics>(G,-150);
        auto* ToLocal=Add<UAnimGraphNode_ComponentToLocalSpace>(G,400);
        auto& D=Dynamics->Node;
        D.BoundBone.BoneName=TEXT("strap_01");D.ChainEnd.BoneName=TEXT("strap_05");D.bChain=true;
        D.SimulationSpace=AnimPhysSimSpaceType::Component;
        D.bAngularSpring=true;D.AngularSpringConstant=20.f;D.bLinearSpring=false;
        D.bUsePlanarLimit=false;D.bUseSphericalLimits=false;D.bEnableWind=false;
        D.bOverrideLinearDamping=true;D.bOverrideAngularDamping=true;
        D.LinearDampingOverride=D.AngularDampingOverride=1.f-FMath::Exp(-1.5f);
        D.ComponentLinearAccScale=FVector(1);D.ComponentLinearVelScale=FVector::ZeroVector;
        D.ComponentAppliedLinearAccClamp=FVector(3000);
        D.SimSpaceSettings.SimSpaceAngularAlpha=1.f;
        D.SimSpaceSettings.MaxAngularVelocity=10.f;D.SimSpaceSettings.MaxAngularAcceleration=100.f;
        D.NumSolverIterationsPreUpdate=8;D.NumSolverIterationsPostUpdate=2;
        D.GravityScale=1.f;D.PhysicsBodyDefinitions.SetNum(5);
        const auto& Skeleton=Mesh->GetRefSkeleton();
        for(int32 I=0;I<5;++I){
            auto& Body=D.PhysicsBodyDefinitions[I];
            Body.BoundBone.BoneName=FName(*FString::Printf(TEXT("strap_%02d"),I+1));
            const FName Next=I==4?FName(TEXT("strap_tip")):FName(*FString::Printf(TEXT("strap_%02d"),I+2));
            const int32 Child=Skeleton.FindBoneIndex(Next);if(Child==INDEX_NONE)return;
            const FVector Segment=Skeleton.GetRefBonePose()[Child].GetTranslation();
            Body.LocalJointOffset=Segment*.5;Body.BoxExtents=FVector(2)+Segment.GetSafeNormal().GetAbs()*Segment.Length();
            Body.ConstraintSetup.AngularTarget=FVector::YAxisVector;
            Body.ConstraintSetup.AngularTargetAxis=Body.ConstraintSetup.TwistAxis=AnimPhysTwistAxis::AxisY;
            Body.ConstraintSetup.AngularLimitsMin=FVector(-65);Body.ConstraintSetup.AngularLimitsMax=FVector(65);
        }
        Dynamics->bPreviewLive=true;Dynamics->bShowAngularLimits=true;
        Dynamics->NodeComment=TEXT("Tune the strap here: Physics Body Definitions for each joint; spring and damping below. Component switches still control distance and enable/disable. No external collisions.");
        Dynamics->bCommentBubbleVisible=true;
        if(!Connect(G,Ref,ToComponent)||!Connect(G,ToComponent,Dynamics)||!Connect(G,Dynamics,ToLocal)||!Connect(G,ToLocal,Root)){
            UE_LOG(LogTemp,Error,TEXT("HolsterAnimBlueprint: pose connection failed; asset left unsaved"));return;
        }
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
        FKismetEditorUtilities::CompileBlueprint(BP);
        BP->MarkPackageDirty();
    }
    if(!BP)return;
    FString Report=FString::Printf(TEXT("asset=%s status=%d class=%s\n"),*BP->GetPathName(),int32(BP->Status),*GetPathNameSafe(BP->GeneratedClass));
    for(UEdGraph* G:BP->FunctionGraphs)for(UEdGraphNode* N:G->Nodes){
        Report+=FString::Printf(TEXT("node=%s\n"),*N->GetClass()->GetName());
        if(auto* A=Cast<UAnimGraphNode_AnimDynamics>(N)){
            if(Args.Contains(TEXT("LinkLimits"))){
                const FScopedTransaction Transaction(NSLOCTEXT("HolsterAnimBlueprint","LinkLimits","Link strap joint constraints"));
                BP->Modify();A->Modify();
                BP->GetPackage()->GetMetaData().SetValue(BP,SharedKey,TEXT("1"));
                CopyConstraints(A,0);
                A->NodeComment=TEXT("Joint constraints are linked: edit Constraint Setup in any Body Definition to update all five. Bone, size and pivot stay individual. Compile and Save after tuning.");
                A->bCommentBubbleVisible=true;
                FBlueprintEditorUtils::MarkBlueprintAsModified(BP);
            }
            if(Args.Contains(TEXT("UnlinkLimits"))){
                BP->GetPackage()->GetMetaData().SetValue(BP,SharedKey,TEXT("0"));BP->MarkPackageDirty();
            }
            if(Args.Contains(TEXT("TestLinks"))){
                auto* Fixture=NewObject<UAnimGraphNode_AnimDynamics>(A->GetGraph(),NAME_None,RF_Transient);
                Fixture->Node=A->Node;
                const auto Before=Fixture->Node.PhysicsBodyDefinitions;
                bool Passed=Before.Num()==5;
                for(int32 Index=0;Index<Before.Num();++Index){
                    auto& Source=Fixture->Node.PhysicsBodyDefinitions[Index];
                    Source.ConstraintSetup.AngularLimitsMin=FVector(-7-Index,-20-Index,-31-Index);
                    Source.ConstraintSetup.AngularLimitsMax=FVector(9+Index,22+Index,33+Index);
                    const auto Expected=Source.ConstraintSetup;
                    FPropertyChangedEvent Event(FindFProperty<FProperty>(FAnimPhysConstraintSetup::StaticStruct(),TEXT("AngularLimitsMin")),EPropertyChangeType::ValueSet);
                    TArray<TMap<FString,int32>> Indices;Indices.Add({{TEXT("PhysicsBodyDefinitions"),Index}});
                    Event.SetArrayIndexPerObject(Indices);Event.ObjectIteratorIndex=0;
                    FCoreUObjectDelegates::OnObjectPropertyChanged.Broadcast(Fixture,Event);
                    for(int32 J=0;J<Before.Num();++J){
                        const auto& Body=Fixture->Node.PhysicsBodyDefinitions[J];
                        Passed&=FAnimPhysConstraintSetup::StaticStruct()->CompareScriptStruct(&Body.ConstraintSetup,&Expected,0)
                            &&Body.BoxExtents==Before[J].BoxExtents&&Body.LocalJointOffset==Before[J].LocalJointOffset
                            &&Body.BoundBone.BoneName==Before[J].BoundBone.BoneName;
                    }
                }
                Report+=FString::Printf(TEXT("shared_edit_event_test=%s sources=%d geometry_preserved=%d\n"),Passed?TEXT("PASS"):TEXT("FAIL"),Before.Num(),Passed);
            }
            Report+=FString::Printf(TEXT("shared_constraints=%s\n"),*BP->GetPackage()->GetMetaData().GetValue(BP,SharedKey));
            Report+=FString::Printf(TEXT("bodies=%d spring=%g damping=%g\n"),A->Node.PhysicsBodyDefinitions.Num(),A->Node.AngularSpringConstant,A->Node.AngularDampingOverride);
            for(const auto& Body:A->Node.PhysicsBodyDefinitions)
                Report+=FString::Printf(TEXT("body=%s min=%s max=%s box=%s pivot=%s\n"),*Body.BoundBone.BoneName.ToString(),*Body.ConstraintSetup.AngularLimitsMin.ToString(),*Body.ConstraintSetup.AngularLimitsMax.ToString(),*Body.BoxExtents.ToString(),*Body.LocalJointOffset.ToString());
            if(Args.Contains(TEXT("Open")))FKismetEditorUtilities::BringKismetToFocusAttentionOnObject(A);
        }
        for(auto* P:N->Pins)if(P->Direction==EGPD_Output)for(auto* To:P->LinkedTo)
            Report+=FString::Printf(TEXT("link=%s.%s -> %s.%s\n"),*N->GetName(),*P->PinName.ToString(),*To->GetOwningNode()->GetName(),*To->PinName.ToString());
    }
    FFileHelper::SaveStringToFile(Report,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/HolsterStrap20261013/anim-blueprint.txt")));
    UE_LOG(LogTemp,Display,TEXT("HolsterAnimBlueprint: %s"),*Report);
}
FAutoConsoleCommand Command(TEXT("Prophecy.Editor.HolsterAnimBlueprint"),TEXT("Create (only if missing), inspect, Open, LinkLimits or UnlinkLimits on the cosmetic strap AnimBlueprint."),FConsoleCommandWithArgsDelegate::CreateStatic(&Run));
}
