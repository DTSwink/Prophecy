#include "Misc/AutomationTest.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "HAL/PlatformTime.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBreathingTest,"Prophecy.Breathing.BakedIdle",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBreathingTest::RunTest(const FString&)
{
    using namespace ProphecyBreathing;
    FString Text;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/Breathing20261014/idle.json")))){
        AddError(TEXT("Run Tools/NN/ExportBreathing.py first."));return false;
    }
    TSharedPtr<FJsonObject> J;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),J))return false;
    auto Transform=[](const TSharedPtr<FJsonValue>& V){const auto& X=V->AsArray();return FTransform(
        FQuat(X[3]->AsNumber(),X[4]->AsNumber(),X[5]->AsNumber(),X[6]->AsNumber()).GetNormalized(),FVector(X[0]->AsNumber(),X[1]->AsNumber(),X[2]->AsNumber()));};
    TArray<FName> Names;TArray<int32> Parents;TArray<FTransform> BaseLocal,Base;
    const auto& Raw=J->GetArrayField(TEXT("raw"));
    for(int I=0;I<17;++I){Names.Add(FName(*J->GetArrayField(TEXT("names"))[I]->AsString()));Parents.Add(int(J->GetArrayField(TEXT("parents"))[I]->AsNumber()));BaseLocal.Add(Transform(Raw[0]->AsArray()[I]));}
    for(int I=0;I<8;++I){Names.Add(FName(*J->GetArrayField(TEXT("legs"))[I]->AsString()));Parents.Add(I%4==0?0:16+I);BaseLocal.Add(Transform(J->GetArrayField(TEXT("leg_local"))[I]));}
    for(int I=0;I<25;++I)Base.Add(Parents[I]<0?BaseLocal[I]:BaseLocal[I]*Base[Parents[I]]);
    const FLayout Layout=Layouts[LayoutFor(Names,Parents)];
    double Position=0,Angle=0,Length=0;int SamplesChecked=0;
    for(bool Pelvis:{false,true})for(int Tick=0;Tick<600;++Tick){
        auto Pose=Base;auto Local=BaseLocal;ApplySample(Layout,0,Tick*10,Pelvis,Pose,Local);
        FTransform Expected[17];
        for(int I=0;I<17;++I){const auto T=Transform(Raw[Tick]->AsArray()[I]);
            Expected[I]=I==0?(Pelvis?T:Base[0]):T*Expected[Parents[I]];
            Position=FMath::Max(Position,FVector::Distance(Expected[I].GetLocation(),Pose[I].GetLocation()));
            Angle=FMath::Max(Angle,FMath::RadiansToDegrees(Expected[I].GetRotation().AngularDistance(Pose[I].GetRotation())));
        }
        for(int S=0;S<2;++S){const int H=17+S*4,K=H+1,F=H+2;
            TestTrue(TEXT("Feet/toes unchanged"),Pose[F].Equals(Base[F],0)&&Pose[F+1].Equals(Base[F+1],0));
            Length=FMath::Max(Length,FMath::Abs(FVector::Distance(Pose[H].GetLocation(),Pose[K].GetLocation())-FVector::Distance(Base[H].GetLocation(),Base[K].GetLocation())));
            Length=FMath::Max(Length,FMath::Abs(FVector::Distance(Pose[K].GetLocation(),Pose[F].GetLocation())-FVector::Distance(Base[K].GetLocation(),Base[F].GetLocation())));
            if(!Pelvis)for(int B=H;B<=F+1;++B)TestTrue(TEXT("Upper mode leaves every lower transform unchanged"),Pose[B].Equals(Base[B],0));
        }
        ++SamplesChecked;
    }
    TestTrue(TEXT("Independent raw idle reconstruction position"),Position<.0001);
    TestTrue(TEXT("Independent raw idle reconstruction rotation"),Angle<.0001);
    TestTrue(TEXT("Planted leg lengths"),Length<.0001);
    // Independent region gains scale angle and displacement, not quaternion
    // components; zero leaves local motion intact even when its parent moves.
    for(float Gain:{0.f,.5f,2.f,5.f})for(int Bone=0;Bone<17;++Bone){
        const auto Unit=Offset(BaseLocal[Bone],210,230,Bone);
        const auto Scaled=Offset(BaseLocal[Bone],210,230,Bone,Gain);
        TestTrue(TEXT("Multiplier scales displacement"),Scaled.GetLocation().Equals(
            BaseLocal[Bone].GetLocation()+Gain*(Unit.GetLocation()-BaseLocal[Bone].GetLocation()),1.e-8));
        const double UnitAngle=BaseLocal[Bone].GetRotation().AngularDistance(Unit.GetRotation());
        TestTrue(TEXT("Multiplier scales angle"),FMath::Abs(BaseLocal[Bone].GetRotation().AngularDistance(Scaled.GetRotation())-Gain*UnitAngle)<1.e-6);
    }
    for(const FVector2D Gain:{FVector2D(0,3),FVector2D(3,0),FVector2D(3,2)}){
        auto Pose=Base;auto Local=BaseLocal;ApplySample(Layout,210,230,true,Pose,Local,Gain.X,Gain.Y);
        if(Gain.X==0)for(int B:{0,17,18,19,20,21,22,23,24})TestTrue(TEXT("Zero pelvis gain leaves lower body exact"),Pose[B].Equals(Base[B],0));
        for(int B=1;B<17;++B)TestTrue(TEXT("Upper gain independent of pelvis gain"),Local[B].Equals(Offset(BaseLocal[B],210,230,B,Gain.Y),1.e-8));
        for(int B:{19,20,23,24})TestTrue(TEXT("Amplified pelvis keeps feet exact"),Pose[B].Equals(Base[B],0));
    }
    // PHAT order can differ from hierarchy order, including neck_02 after head.
    TArray<FName> ShuffledNames;TArray<int32> ShuffledParents;TArray<FTransform> Shuffled;
    for(int I=24;I>=0;--I){ShuffledNames.Add(Names[I]);ShuffledParents.Add(Parents[I]<0?-1:24-Parents[I]);Shuffled.Add(Base[I]);}
    const FLayout ShuffledLayout=Layouts[LayoutFor(ShuffledNames,ShuffledParents)];
    auto Expected=Base;ApplySample(Layout,0,2370,true,Expected);ApplySample(ShuffledLayout,0,2370,true,Shuffled);
    for(int I=0;I<25;++I)TestTrue(TEXT("Hierarchy independent of PHAT order"),Expected[I].Equals(Shuffled[24-I],1.e-8));

    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=World->SpawnActor<AProphecyAgent>();
    auto C=Base,L=BaseLocal;
    auto Run=[&](uint64 Tick,bool Eligible){return Apply(A,Tick,Eligible,Names,Parents,C,L);};
    TestTrue(TEXT("Default mode"),UProphecyBreathingLibrary::GetBreathingMode(A)==EProphecyBreathingMode::UpperAndPelvis);
    Run(10,true);TestTrue(TEXT("Entry is identity"),C[0].Equals(Base[0],0));
    for(int Tick=1;Tick<=1200;++Tick){
        Run(10+Tick,true);
        auto Once=C;Run(10+Tick,true);
        for(int B=0;B<25;++B)TestTrue(TEXT("Repeated publication cannot add delta twice"),C[B].Equals(Once[B],0));
        if(Tick%600==0)for(int B=0;B<17;++B)TestTrue(TEXT("Two incremental loops do not accumulate offset"),C[B].Equals(Base[B],1.e-4));
    }
    Run(1310,true);const auto AtStop=C;
    Run(1312,false);
    for(int B=0;B<25;++B)TestTrue(TEXT("Action/movement entry preserves accepted pose; no offset subtraction"),C[B].Equals(AtStop[B],0));
    TestFalse(TEXT("Gate retires phase"),States[A].Active);
    Run(1400,true);TestEqual(TEXT("New idle starts from zero"),States[A].Start,uint64(1400));
    for(int B=0;B<25;++B)TestTrue(TEXT("Restart preserves the actual pose"),C[B].Equals(AtStop[B],0));
    UProphecyBreathingLibrary::SetBreathingMode(A,EProphecyBreathingMode::None);
    Run(1420,true);
    for(int B=0;B<25;++B)TestTrue(TEXT("Mode off preserves the actual pose"),C[B].Equals(AtStop[B],0));
    UProphecyBreathingLibrary::SetBreathingMode(A,EProphecyBreathingMode::UpperOnly);
    Run(1500,true);Run(1600,true);Reset(A);Run(2000,true);TestEqual(TEXT("Reset restarts phase"),States[A].Start,uint64(2000));
    const uint64 PhaseStart=States[A].Start;
    TestTrue(TEXT("Set region multipliers"),UProphecyBreathingLibrary::SetBreathingMultipliers(A,3.f,2.f));
    TestEqual(TEXT("Gain change retains phase"),States[A].Start,PhaseStart);
    TestEqual(TEXT("Pelvis gain stored"),States[A].PelvisMultiplier,3.f);
    TestEqual(TEXT("Upper gain stored"),States[A].UpperBodyMultiplier,2.f);
    UProphecyBreathingLibrary::SetBreathingMultipliers(A,0.f,0.f);const auto Zero=C;
    TestTrue(TEXT("Zero gains skip publication work"),Run(2002,true)==EProphecyBreathingMode::None);
    for(int B=0;B<25;++B)TestTrue(TEXT("Zero gains leave accepted pose untouched"),C[B].Equals(Zero[B],0));

    FString FineText;
    TSharedPtr<FJsonObject> Fine;
    if(!FFileHelper::LoadFileToString(FineText,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/BreathingSpeed20261014/idle-fine.json")))||
       !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(FineText),Fine)){
        AddError(TEXT("Run the breathing exporter for the fractional-time oracle."));Remove(A);World->DestroyWorld(false);return false;
    }
    const auto& FineRaw=Fine->GetArrayField(TEXT("raw"));
    UProphecyBreathingLibrary::SetBreathingMode(A,EProphecyBreathingMode::UpperOnly);
    UProphecyBreathingLibrary::SetBreathingMultipliers(A,1.f,1.f);
    double SpeedPosition=0,SpeedAngle=0;
    // Each exact rational rate crosses the seam and returns to phase zero.
    // Compare the accumulated runtime result against raw clip evaluation,
    // including the 0.7 rate whose tick-aligned period spans seven cycles.
    for(int Step=3;Step<=10;++Step){
        TestTrue(TEXT("Speed setter selects every baked rate"),FMath::IsNearlyEqual(
            UProphecyBreathingLibrary::SetBreathingSpeedMultiplier(A,Step*.1f),Step*.1f));
        Reset(A);C=Base;L=BaseLocal;Run(10000,true);
        int Period=1;while((Period*Step)%Phases!=0)++Period;
        for(int N=1;N<=Period;++N){
            Run(10000+N,true);const int Phase=(N*Step)%Phases;
            TestEqual(TEXT("Exact tick-based speed phase"),States[A].Phase,Phase);
            FTransform ExpectedPose[17];ExpectedPose[0]=Base[0];
            for(int B=1;B<17;++B){
                ExpectedPose[B]=Transform(FineRaw[Phase]->AsArray()[B])*ExpectedPose[Parents[B]];
                SpeedPosition=FMath::Max(SpeedPosition,FVector::Dist(ExpectedPose[B].GetLocation(),C[B].GetLocation()));
                SpeedAngle=FMath::Max(SpeedAngle,FMath::RadiansToDegrees(ExpectedPose[B].GetRotation().AngularDistance(C[B].GetRotation())));
            }
        }
        for(int B=0;B<25;++B)TestTrue(TEXT("Every speed loops without accumulated offset"),C[B].Equals(Base[B],.0001));
    }
    TestTrue(TEXT("All speed paths match raw clip position"),SpeedPosition<.0001);
    TestTrue(TEXT("All speed paths match raw clip rotation"),SpeedAngle<.0001);
    for(const FVector2D Pair:{FVector2D(-10,.3),FVector2D(.34,.3),FVector2D(.35,.4),FVector2D(.76,.8),FVector2D(.99,1),FVector2D(100,1)})
        TestTrue(TEXT("Nearest rate with bounds"),FMath::IsNearlyEqual(double(UProphecyBreathingLibrary::SetBreathingSpeedMultiplier(A,Pair.X)),Pair.Y,1.e-6));
    TestEqual(TEXT("Invalid agent rejected"),UProphecyBreathingLibrary::SetBreathingSpeedMultiplier(nullptr,.5f),0.f);

    UProphecyBreathingLibrary::SetBreathingMode(A,EProphecyBreathingMode::UpperAndPelvis);
    UProphecyBreathingLibrary::SetBreathingSpeedMultiplier(A,.3f);
    UProphecyBreathingLibrary::SetBreathingMultipliers(A,2.f,3.f);
    Reset(A);C=Base;L=BaseLocal;Run(20000,true);Run(20013,true);
    const int OldPhase=States[A].Phase;const auto BeforeSpeed=C;
    UProphecyBreathingLibrary::SetBreathingSpeedMultiplier(A,.8f);
    TestEqual(TEXT("Speed change keeps current phase"),States[A].Phase,OldPhase);
    TestEqual(TEXT("Speed change keeps pelvis amplitude"),States[A].PelvisMultiplier,2.f);
    TestEqual(TEXT("Speed change keeps upper amplitude"),States[A].UpperBodyMultiplier,3.f);
    Run(20013,true);
    for(int B=0;B<25;++B)TestTrue(TEXT("Setter/repeated tick cannot move the pose"),C[B].Equals(BeforeSpeed[B],0));
    auto ExpectedSpeed=C,ExpectedLocal=L;
    ApplySample(Layout,OldPhase,(OldPhase+16)%Phases,true,ExpectedSpeed,ExpectedLocal,2.f,3.f);
    Run(20015,true);
    for(int B=0;B<25;++B)TestTrue(TEXT("Changed speed and both amplitudes apply only the next elapsed interval"),C[B].Equals(ExpectedSpeed[B],1.e-8));
    for(int B:{19,20,23,24})TestTrue(TEXT("Slower amplified breathing keeps feet planted"),C[B].Equals(Base[B],0));
    Reset(A);Run(30000,true);TestEqual(TEXT("Reset preserves speed"),States[A].SpeedStep,8);
    TestEqual(TEXT("Reset restarts phase at selected speed"),States[A].Phase,0);
    AddInfo(FString::Printf(TEXT("All eight speeds: raw oracle position %.12g cm / rotation %.12g deg"),SpeedPosition,SpeedAngle));
    Remove(A);World->DestroyWorld(false);

    // 100-pose publication workload: one new endpoint, preallocated scratch,
    // warm table. Includes pose copying; does not include NN/physics/rendering.
    double Times[2]={};FTransform Current[25],Locals[25];double Checksum=0;
    for(int Mode=0;Mode<2;++Mode){TArray<double> Measurements;
        for(int Repeat=0;Repeat<5;++Repeat){const double Start=FPlatformTime::Seconds();
            for(int Batch=0;Batch<120;++Batch)for(int Agent=0;Agent<100;++Agent){
                FMemory::Memcpy(Current,Base.GetData(),sizeof(Current));FMemory::Memcpy(Locals,BaseLocal.GetData(),sizeof(Locals));
                const int Tick=1+(Batch*2+Agent)%599;
                ApplySample(Layout,Tick*10,((Tick+2)%600)*10,Mode==1,MakeArrayView(Current),MakeArrayView(Locals));
                Checksum+=Current[16].GetLocation().X;
            }
            Measurements.Add((FPlatformTime::Seconds()-Start)*1000./120.);
        }Measurements.Sort();Times[Mode]=Measurements[2];
    }
    const FString Report=FString::Printf(TEXT("samples=%d position_cm=%.12g angle_deg=%.12g length_cm=%.12g\n100_agent_publication_upper_ms=%.9f upper_pelvis_ms=%.9f checksum=%.9g\nshared_table_bytes=%llu\n"),
        SamplesChecked,Position,Angle,Length,Times[0],Times[1],Checksum,uint64(sizeof(ProphecyBreathingData::Samples)));
    AddInfo(Report);FFileHelper::SaveStringToFile(Report,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/BreathingHistory20261014/native-results.txt")));
    return true;
}
