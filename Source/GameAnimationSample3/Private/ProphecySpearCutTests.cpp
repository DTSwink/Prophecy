#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#include "PhysicsEngine/BodySetup.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"
#include "UObject/UnrealType.h"
#include "ProphecySpearCutGeometry.h"
#include "ProphecyJoltBlueprintLibrary.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltSceneCollisionComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltConstraintRuntime.h"

namespace SpearTests
{
FProperty* Field(UStruct* S,const TCHAR* Name)
{for(TFieldIterator<FProperty> I(S);I;++I)if(I->GetName()==Name||I->GetName().StartsWith(FString(Name)+TEXT("_")))return *I;return nullptr;}
double Number(UObject* O,const TCHAR* Name)
{auto* P=CastField<FNumericProperty>(Field(O->GetClass(),Name));return P?P->GetFloatingPointPropertyValue(P->ContainerPtrToValuePtr<void>(O)):0;}
void Set(FProperty* P,void* Container,double Value)
{if(auto* N=CastField<FNumericProperty>(P)){void* V=N->ContainerPtrToValuePtr<void>(Container);if(N->IsInteger())N->SetIntPropertyValue(V,int64(Value));else N->SetFloatingPointPropertyValue(V,Value);}}
void Object(FProperty* P,void* Container,UObject* Value)
{if(auto* O=CastField<FObjectPropertyBase>(P))O->SetObjectPropertyValue_InContainer(Container,Value);}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSpearGeometryTest,"Prophecy.Spear.PassThroughGeometry",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FSpearGeometryTest::RunTest(const FString&)
{
    using namespace ProphecySpearCut;
    const double Scale=.7619161867885869,Rear=-108.96251201629639,Root=(116.2606120109558-46.96560204029083)*Scale;
    const double Exit=ForwardExit(Rear,Scale,Root,15);
    TestTrue(TEXT("Full spear and target determine forward exit"),FMath::IsNearlyEqual(Exit,Rear*Scale-Root-15,1.e-8));
    TestFalse(TEXT("Tip emerging is not whole-weapon clearance"),Cleared(20,36,true,Exit));
    TestFalse(TEXT("Passing blade root does not release shaft"),Cleared(-1,36,true,Exit));
    TestFalse(TEXT("Rear still inside final target thickness"),Cleared(Exit+7,36,true,Exit));
    TestFalse(TEXT("At far face, retain small clearance tolerance"),Cleared(Exit,36,true,Exit));
    TestTrue(TEXT("Rear beyond far face releases"),Cleared(Exit-.1,36,true,Exit));
    TestTrue(TEXT("High-speed crossing still releases"),Cleared(Exit-100,36,true,Exit));
    TestTrue(TEXT("Withdrawal still releases at tip"),Cleared(36.1,36,true,Exit));
    TestFalse(TEXT("Ordinary sword never releases forward"),Cleared(-1000,36,false,Exit));
    TestTrue(TEXT("Target thickness stays world centimetres under weapon scaling"),FMath::IsNearlyEqual(ForwardExit(Rear,2,Root,15)-ForwardExit(Rear,2,Root,30),15.));
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSpearNativeLifecycleTest,"Prophecy.Spear.NativeLifecycle",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FSpearNativeLifecycleTest::RunTest(const FString&)
{
    using namespace SpearTests;
    for(int Case=0;Case<4;++Case)
    {
        const bool Spear=Case!=2,Withdraw=Case==1,RejectSlash=Case==3;
        UClass* Class=LoadClass<AActor>(nullptr,Spear?TEXT("/Game/_mygame/spear/A_Spear.A_Spear_C"):TEXT("/Game/_mygame/sword/A_Sword.A_Sword_C"));
        if(!TestNotNull(TEXT("Saved weapon class"),Class))return false;
        const auto IV=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true).EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
        UWorld* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&IV);
        if(!World)return false;
        GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
        ON_SCOPE_EXIT{World->DestroyWorld(false);GEngine->DestroyWorldContext(World);World->MarkAsGarbage();};
        World->InitializeActorsForPlay(FURL());
        FString Error;
        if(!UProphecyJoltBlueprintLibrary::InitializeJoltWorld(World,Error,64,0)){AddError(Error);return false;}
        FActorSpawnParameters Spawn;Spawn.ObjectFlags|=RF_Transient;Spawn.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        auto* Weapon=World->SpawnActor<AActor>(Class,FTransform::Identity,Spawn);
        if(!TestNotNull(TEXT("Weapon instance"),Weapon))return false;
        auto* Mesh=Cast<UStaticMeshComponent>(CastFieldChecked<FObjectPropertyBase>(Field(Class,TEXT("sword")))->GetObjectPropertyValue_InContainer(Weapon));
        if(!TestNotNull(TEXT("Physical weapon mesh"),Mesh))return false;
        const double Length=Number(Weapon,TEXT("blade length")),Root=Number(Weapon,TEXT("hilt half length"));
        if(Spear)
        {
            TestTrue(TEXT("Saved Throw Lab scale"),Mesh->GetComponentScale().Equals(FVector(.8623427588789339,.8834927125312151,.7619161867885869),1.e-6));
            TestEqual(TEXT("All authored UCX hulls imported"),Mesh->GetStaticMesh()->GetBodySetup()->AggGeom.ConvexElems.Num(),17);
            TestEqual(TEXT("Render topology preserved"),Mesh->GetStaticMesh()->GetNumTriangles(0),43494);
            TestTrue(TEXT("Real centimetre-scale spear"),Mesh->GetStaticMesh()->GetBoundingBox().GetSize().Z>225);
        }
        Mesh->SetWorldLocation(FVector(0,0,500-Root-Length+1));Mesh->SetEnableGravity(false);
        // Same Jolt-compatible policy applied by native equip/standalone setup.
        Mesh->SetUseMACD(false);Mesh->SetUseCCD(true);
        // Isolate the travel/cleanup contract from authored material resistance.
        if(auto* D=FindFProperty<FStructProperty>(Class,TEXT("velocity cut dampings")))
            *D->ContainerPtrToValuePtr<FVector>(Weapon)=FVector::ZeroVector;
        auto* Victim=World->SpawnActor<AActor>();
        auto* Wall=NewObject<UStaticMeshComponent>(Victim,NAME_None,RF_Transient);Victim->AddInstanceComponent(Wall);Victim->SetRootComponent(Wall);
        Wall->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));Wall->SetWorldTransform(FTransform(FQuat::Identity,FVector(0,0,507.5),FVector(2,2,.15)));Wall->SetMobility(EComponentMobility::Static);
        Wall->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);Wall->SetCollisionResponseToAllChannels(ECR_Block);Wall->RegisterComponent();
        auto* Adapter=Weapon->FindComponentByClass<UProphecyJoltBodyComponent>();
        if(!Adapter){Adapter=NewObject<UProphecyJoltBodyComponent>(Weapon);Weapon->AddInstanceComponent(Adapter);Adapter->RegisterComponent();}
        Adapter->bAutomaticStep=false;
        if(!Adapter->EnableBody(*Mesh,Error)){AddError(Error);return false;}
        auto* Scene=NewObject<UProphecyJoltSceneCollisionComponent>(Victim);Victim->AddInstanceComponent(Scene);Scene->bAutomaticScenePhysics=false;Scene->RegisterComponent();
        if(!Scene->EnableSceneCollision(Error)){AddError(Error);return false;}
        auto* Joint=NewObject<UPhysicsConstraintComponent>(Weapon,NAME_None,RF_Transient);Weapon->AddInstanceComponent(Joint);Joint->SetWorldLocation(FVector(0,0,500));Joint->RegisterComponent();
        Joint->SetDisableCollision(true);Joint->SetConstrainedComponents(Wall,NAME_None,Mesh,NAME_None);
        auto* Array=FindFProperty<FArrayProperty>(Class,TEXT("cuts"));UScriptStruct* Struct=CastFieldChecked<FStructProperty>(Array->Inner)->Struct;
        FScriptArrayHelper Cuts(Array,Array->ContainerPtrToValuePtr<void>(Weapon));void* Record=Cuts.GetRawPtr(Cuts.AddValue());
        Object(Field(Struct,TEXT("constraint")),Record,Joint);Object(Field(Struct,TEXT("victimcomp")),Record,Wall);Object(Field(Struct,TEXT("victim")),Record,Victim);
        Set(Field(Struct,TEXT("typecut")),Record,RejectSlash?1:0);Set(Field(Struct,TEXT("typematter")),Record,1);Set(Field(Struct,TEXT("id")),Record,123);
        ProphecyJolt::Constraints::Prepare(World);
        const bool Admitted=ProphecyJolt::Constraints::StartOptimisedSwordCut(Weapon,Joint);
        if(RejectSlash)
        {TestFalse(TEXT("Native guard rejects spear slash"),Admitted);TestEqual(TEXT("Rejected cut record removed"),Cuts.Num(),0);Scene->DisableSceneCollision();Adapter->DisableBody();continue;}
        if(!TestTrue(TEXT("Real cut admitted"),Admitted))return false;
        ProphecyJolt::Constraints::SetPikeWoundCorrection(Joint,true);
        if(!Adapter->StepAndPublish(1.f/60,Error)){AddError(Error);return false;}
        FProphecyJoltJointHandle Handle;FProphecyJoltJointSettings Settings;
        auto* Native=World->GetSubsystem<UProphecyJoltWorldSubsystem>();
        if(!TestTrue(TEXT("Real solver joint"),ProphecyJolt::Constraints::GetJoint(Joint,Handle,Error)))return false;
        Native->ReadJoint(Handle,Settings);
        TestEqual(TEXT("Axial motion policy"),Settings.Translation[2].Motion,Spear?EProphecyJoltAxisMotion::Free:EProphecyJoltAxisMotion::Limited);
        Adapter->SetBodyVelocity(FVector(0,0,Withdraw?-500:500),FVector::ZeroVector,true,Error);
        bool CrossedRoot=false,Released=false;
        for(int Step=0;Step<70;++Step)
        {
            if(!Adapter->StepAndPublish(1.f/60,Error)){AddError(Error);return false;}
            const double Travel=500-(Mesh->GetComponentLocation().Z+Root);
            CrossedRoot|=Travel<-1;
            if(Cuts.Num()==0)
            {
                Released=true;
                if(Withdraw)TestTrue(TEXT("Withdrawal releases after tip clearance"),Travel>Length);
                else
                {FVector Min,Max;Mesh->GetLocalBounds(Min,Max);TestTrue(TEXT("Forward release waits for rear + 15cm"),Travel<ProphecySpearCut::ForwardExit(Min.Z,Mesh->GetComponentScale().Z,Root,15));}
                break;
            }
        }
        if(Spear){TestTrue(TEXT("Spear cut released"),Released);if(!Withdraw)TestTrue(TEXT("Spear crosses former hilt stop"),CrossedRoot);TestFalse(TEXT("Released joint retired"),Native->OwnsJoint(Handle));}
        else{TestFalse(TEXT("Sword still stops at hilt"),CrossedRoot);TestFalse(TEXT("Sword does not release forward"),Released);Joint->DestroyComponent();}
        Scene->DisableSceneCollision();Adapter->DisableBody();
    }
    return !HasAnyErrors();
}
#endif
