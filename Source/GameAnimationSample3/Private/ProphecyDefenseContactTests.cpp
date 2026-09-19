#include "ProphecyDefenseContacts.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "ProphecyJoltContactShape.h"
#include "PhysicsEngine/BodySetup.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyPhysicalContactShapeTest,"Prophecy.NN.Defense.PhysicalContactShapes",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyPhysicalContactShapeTest::RunTest(const FString&)
{
    auto* Capsule=NewObject<UBodySetup>();FKSphylElem C;C.Radius=10;C.Length=20;Capsule->AggGeom.SphylElems.Add(C);
    auto* Sphere=NewObject<UBodySetup>();FKSphereElem S;S.Radius=1;Sphere->AggGeom.SphereElems.Add(S);
    FProphecyJoltContactShape A,B;FString Error;float Time=0;
    if (!A.Build(*Capsule,FVector::OneVector,Error) || !B.Build(*Sphere,FVector::OneVector,Error)) { AddError(Error);return false; }
    auto At=[](double X,double Y,double Z) { return FTransform(FVector(X,Y,Z)); };
    TestFalse(TEXT("Capsule corner is empty (would intersect its bounding box)"),A.Sweep(At(0,0,0),At(0,0,0),B,At(9,9,18),At(9,9,18),Time));
    TestTrue(TEXT("Actual capsule surface contact"),A.Sweep(At(0,0,0),At(0,0,0),B,At(10.5,0,0),At(10.5,0,0),Time));
    TestTrue(TEXT("Fast crossing detected despite clear endpoints"),A.Sweep(At(0,0,0),At(0,0,0),B,At(-100,0,0),At(100,0,0),Time));
    TestTrue(TEXT("Crossing time matches authored radii"),FMath::Abs(Time-.445f)<.0001f);
    TestFalse(TEXT("Parallel near miss is not enlarged"),A.Sweep(At(0,0,0),At(0,0,0),B,At(-100,11.1,0),At(100,11.1,0),Time));
    TestFalse(TEXT("Equal fast translations preserve separation"),A.Sweep(At(0,0,0),At(1000,0,0),B,At(20,0,0),At(1020,0,0),Time));
    auto* Sword=NewObject<UBodySetup>();FKBoxElem Box;Box.Center=FVector(50,0,0);Box.X=100;Box.Y=2;Box.Z=2;Sword->AggGeom.BoxElems.Add(Box);
    FProphecyJoltContactShape Blade;if (!Blade.Build(*Sword,FVector::OneVector,Error)) { AddError(Error);return false; }
    // Less than 180 degrees: the shortest-arc direction must be unambiguous.
    const FTransform R0(FQuat(FVector::UpVector,-FMath::DegreesToRadians(80.)),FVector::ZeroVector),R1(FQuat(FVector::UpVector,FMath::DegreesToRadians(80.)),FVector::ZeroVector);
    TestTrue(TEXT("Sword occupies its authored location"),Blade.Sweep(FTransform::Identity,FTransform::Identity,B,At(80,0,0),At(80,0,0),Time));
    TestTrue(TEXT("Rotating sword catches contact between endpoints"),Blade.Sweep(R0,R1,B,At(80,0,0),At(80,0,0),Time));
    TestTrue(TEXT("Angular contact occurs around the middle"),Time>.45f && Time<.55f);
    if (!B.Build(*Sphere,FVector(2),Error)) { AddError(Error);return false; }
    TestTrue(TEXT("Authored scale applied once"),A.Sweep(At(0,0,0),At(0,0,0),B,At(11.5,0,0),At(11.5,0,0),Time));
    TestFalse(TEXT("No extra scale/enlargement"),A.Sweep(At(0,0,0),At(0,0,0),B,At(12.1,0,0),At(12.1,0,0),Time));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDefenseContactTest,"Prophecy.NN.Defense.ParryContacts",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDefenseContactTest::RunTest(const FString&)
{
    using namespace ProphecyDefense;
    const FString Dir=FPaths::ProjectSavedDir()/TEXT("DefenseIntegration/Models");
    FString Text,Error;FContactGeometry G;TSharedPtr<FJsonObject> Doc;
    if (!G.Load(Dir/TEXT("parry_colliders.json"),Error)) { AddError(Error);return false; }
    if (!FFileHelper::LoadFileToString(Text,*(Dir/TEXT("parry_contact_reference.json"))) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Doc) || !Doc)
    { AddError(TEXT("Run ExportDefenseContactReference.py first."));return false; }
    auto Tensor=[&](const TSharedPtr<FJsonObject>& O,const TCHAR* Name,float* Out,int32 Size)
    {
        const auto& A=O->GetArrayField(Name);if (A.Num()!=Size) { AddError(TEXT("Invalid contact fixture size."));return false; }
        for (int32 I=0;I<Size;++I) Out[I]=float(A[I]->AsNumber());return true;
    };
    float Maximum=0;
    auto Compare=[&](const float* Actual,const float* Expected,int32 Count,const FString& Stage)
    {
        for (int32 I=0;I<Count;++I)
        {
            const float D=FMath::Abs(Actual[I]-Expected[I]);Maximum=FMath::Max(Maximum,D);
            if (!FMath::IsFinite(Actual[I]) || D>1.e-5f+1.e-5f*FMath::Abs(Expected[I]))
            { AddError(FString::Printf(TEXT("%s channel %d %.9g expected %.9g"),*Stage,I,Actual[I],Expected[I]));return false; }
        }
        return true;
    };
    FDefenseBox Previous[20],Current[20],PreviousAttack;FFirstContact Order;float Half[3];double PreviousTime=0;
    if (!Tensor(Doc,TEXT("attacker_half"),Half,3)) return false;
    const uint32 Present=G.PresentMask(true);
    int32 Frame=0,Pairs=0;TArray<TSharedPtr<FJsonValue>> Events;
    for (const auto& V:Doc->GetArrayField(TEXT("frames")))
    {
        const auto F=V->AsObject();float P[75],R[225],C[60],A[180],AC[3],AR[9];
        if (!Tensor(F,TEXT("positions"),P,75) || !Tensor(F,TEXT("rotations"),R,225) || !Tensor(F,TEXT("centers"),C,G.Count*3)
            || !Tensor(F,TEXT("axes"),A,G.Count*9) || !Tensor(F,TEXT("attacker_center"),AC,3) || !Tensor(F,TEXT("attacker_axes"),AR,9)) return false;
        FPose Pose;for (int32 I=0;I<25;++I) { Pose.P[I]=Read(P+I*3);Pose.R[I]=Rows(R+I*9); }
        G.Build(Pose,Current);float ActualC[60],ActualA[180];
        for (int32 I=0;I<G.Count;++I)
        {
            Write(ActualC+I*3,Current[I].Center);
            for (int32 J=0;J<3;++J) Write(ActualA+I*9+J*3,Current[I].Axes.V[J]);
        }
        if (!Compare(ActualC,C,G.Count*3,TEXT("collider centers")) || !Compare(ActualA,A,G.Count*9,TEXT("collider axes"))) return false;
        const FDefenseBox Attack{Read(AC),Rows(AR)};const double Time=F->GetNumberField(TEXT("time"));
        if (Frame)
        {
            for (int32 I=0;I<G.Count;++I) if (Present&(1u<<I))
            {
                const auto Contact=SweepBoxes(Previous[I],Current[I],G.Boxes[I].Half,G.Boxes[I].CenterOffset,
                    PreviousAttack,Attack,Read(Half),FVector3f::ZeroVector);
                Order.Include(Contact,I,PreviousTime,Time);++Pairs;
                if (Contact.bPossible)
                {
                    auto Event=MakeShared<FJsonObject>();Event->SetNumberField(TEXT("frame"),Frame);Event->SetStringField(TEXT("collider"),G.Boxes[I].Name.ToString());
                    Event->SetNumberField(TEXT("fraction"),Contact.Fraction);Event->SetNumberField(TEXT("gap"),Contact.Gap);Event->SetNumberField(TEXT("iterations"),Contact.Iterations);
                    Event->SetBoolField(TEXT("confirmed"),Contact.bConfirmed);Event->SetBoolField(TEXT("resolved"),Contact.bResolved);Events.Add(MakeShared<FJsonValueObject>(Event));
                }
            }
        }
        FMemory::Memcpy(Previous,Current,sizeof(Current));PreviousAttack=Attack;PreviousTime=Time;++Frame;
    }
    TestTrue(TEXT("Saved trajectory has a confirmed contact"),Order.Collider!=INDEX_NONE);
    const double ExpectedTime=Doc->GetNumberField(TEXT("expected_time"));
    TestTrue(TEXT("Saved fractional contact time"),FMath::IsFinite(Order.Time) && FMath::Abs(Order.Time-ExpectedTime)<=1.e-5+1.e-5*FMath::Abs(ExpectedTime));
    auto Report=MakeShared<FJsonObject>();Report->SetNumberField(TEXT("geometry_max_abs"),Maximum);
    Report->SetNumberField(TEXT("contact_time"),FMath::IsFinite(Order.Time)?Order.Time:-1);Report->SetNumberField(TEXT("expected_contact_time"),ExpectedTime);
    Report->SetNumberField(TEXT("unresolved_pairs"),Order.Unresolved);Report->SetArrayField(TEXT("events"),Events);
    FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*(Dir/TEXT("unreal_parry_contact.json")));
    // Cover safety semantics independently of the one supplied sword witness.
    const FRows Identity={{{1,0,0},{0,1,0},{0,0,1}}};
    const FDefenseBox Static{{0,0,0},Identity},FastStart{{-3,0,0},Identity},FastEnd{{3,0,0},Identity};
    const auto Fast=SweepBoxes(Static,Static,{.5f,.5f,.5f},{0,0,0},FastStart,FastEnd,{.5f,.5f,.5f},{0,0,0});
    TestTrue(TEXT("Sweep catches contact absent at either endpoint"),Fast.bConfirmed && FMath::IsNearlyEqual(Fast.Fraction,1.f/3.f,1.e-6f));
    const auto Exhausted=SweepBoxes(Static,Static,{.5f,.5f,.5f},{0,0,0},FastStart,FastEnd,{.5f,.5f,.5f},{0,0,0},1);
    TestTrue(TEXT("Exhaustion cannot confirm a contact"),Exhausted.bPossible && !Exhausted.bConfirmed && !Exhausted.bResolved);
    FFirstContact First;First.Include(Exhausted,2,0,1);
    TestEqual(TEXT("Unconfirmed contact is ignored"),First.Collider,INDEX_NONE);
    First.Include(Fast,0,1,2);First.Include(Fast,1,0,1);
    TestEqual(TEXT("Earliest contact wins regardless of body"),First.Collider,1);
    TestTrue(TEXT("Earliest fractional time"),FMath::IsNearlyEqual(First.Time,double(Fast.Fraction)));
    AddInfo(FString::Printf(TEXT("%d frames / %d swept pairs, collider error %.9g; block %.9f expected %.9f; unresolved %d."),Frame,Pairs,Maximum,Order.Time,ExpectedTime,Order.Unresolved));
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDodgeContactGeometryTest,"Prophecy.NN.Defense.DodgeContactGeometry",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDodgeContactGeometryTest::RunTest(const FString&)
{
    using namespace ProphecyDefense;
    const FString Dir=FPaths::ProjectSavedDir()/TEXT("DefenseIntegration/Models");
    FString Text,Error;FContactGeometry G;TSharedPtr<FJsonObject> Doc;
    if (!G.Load(Dir/TEXT("dodge_colliders.json"),Error)) { AddError(Error);return false; }
    TestEqual(TEXT("Dodge retains its saved 13-box layout"),G.Count,13);
    TestEqual(TEXT("No Parry end-effector boxes"),G.BaseCount,G.Count);
    if (!FFileHelper::LoadFileToString(Text,*(Dir/TEXT("dodge_contact_reference.json")))
        || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Doc) || !Doc) return false;
    auto Tensor=[&](const TSharedPtr<FJsonObject>& O,const TCHAR* Name,float* Out,int32 Size)
    {
        const auto& A=O->GetArrayField(Name);if (A.Num()!=Size) return false;
        for (int32 I=0;I<Size;++I) Out[I]=float(A[I]->AsNumber());return true;
    };
    float Maximum=0;
    for (const auto& V:Doc->GetArrayField(TEXT("frames")))
    {
        const auto F=V->AsObject();float P[75],R[225],C[39],A[117];
        if (!Tensor(F,TEXT("positions"),P,75) || !Tensor(F,TEXT("rotations"),R,225)
            || !Tensor(F,TEXT("centers"),C,39) || !Tensor(F,TEXT("axes"),A,117)) return false;
        FPose Pose;for (int32 I=0;I<25;++I) { Pose.P[I]=Read(P+I*3);Pose.R[I]=Rows(R+I*9); }
        FDefenseBox Boxes[13];G.Build(Pose,Boxes);
        for (int32 I=0;I<13;++I) for (int32 K=0;K<12;++K)
        {
            const float Value=K<3?Boxes[I].Center[K]:Boxes[I].Axes.V[(K-3)/3][(K-3)%3];
            const float Expected=K<3?C[I*3+K]:A[I*9+K-3];
            const float Delta=FMath::Abs(Value-Expected);Maximum=FMath::Max(Maximum,Delta);
            if (!FMath::IsFinite(Value) || Delta>1.e-5f+1.e-5f*FMath::Abs(Expected))
            { AddError(FString::Printf(TEXT("Dodge collider %d channel %d: %.9g expected %.9g"),I,K,Value,Expected));return false; }
        }
    }
    AddInfo(FString::Printf(TEXT("Eight saved Dodge poses, 13 colliders each; max element error %.9g."),Maximum));
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDefenseAttackerTest,"Prophecy.NN.Defense.AttackerAttachments",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDefenseAttackerTest::RunTest(const FString&)
{
    using namespace ProphecyDefense;
    FString Error,Text;FContactGeometry G;TSharedPtr<FJsonObject> Doc;
    if (!G.Load(FPaths::ProjectContentDir()/TEXT("locomotion/NN/defense/attacker_colliders.json"),Error,true))
    { AddError(Error);return false; }
    if (!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/DodgeMismatch/attacker_attachment_reference.json")))
        || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Doc) || !Doc)
    { AddError(TEXT("Missing independent viewer attachment reference."));return false; }
    float MaxError=0;int32 Count=0;
    for (const auto& V:Doc->GetArrayField(TEXT("cases")))
    {
        const auto C=V->AsObject();float P[3],R[9],Expected[15],Actual[15];
        auto ReadArray=[&](const TCHAR* Key,float* Out,int32 N)
        {
            const auto& A=C->GetArrayField(Key);if (A.Num()!=N) return false;
            for (int32 I=0;I<N;++I) Out[I]=float(A[I]->AsNumber());return true;
        };
        if (!ReadArray(TEXT("position"),P,3) || !ReadArray(TEXT("rotation"),R,9)
            || !ReadArray(TEXT("center"),Expected,3) || !ReadArray(TEXT("axes"),Expected+3,9)
            || !ReadArray(TEXT("half"),Expected+12,3)) { AddError(TEXT("Malformed fixture."));return false; }
        const int32 I=int32(C->GetNumberField(TEXT("index")));
        const auto Box=G.BuildAttachedBox(Read(P),Rows(R),I);
        Write(Actual,Box.Center);for (int32 J=0;J<3;++J) Write(Actual+3+J*3,Box.Axes.V[J]);
        Write(Actual+12,G.Boxes[I].Half);
        for (int32 K=0;K<15;++K)
        {
            MaxError=FMath::Max(MaxError,FMath::Abs(Actual[K]-Expected[K]));
            if (!FMath::IsFinite(Actual[K]) || FMath::Abs(Actual[K]-Expected[K])>1.e-5f)
            { AddError(FString::Printf(TEXT("Attachment %d sample %d channel %d mismatch."),I,Count,K));return false; }
        }
        ++Count;
    }
    AddInfo(FString::Printf(TEXT("Compared %d training attacker attachment samples, max error %.9g."),Count,MaxError));
    return Count>0;
}
#endif
