#include "ProphecyBreathing.h"
#include "ProphecyBreathingLibrary.h"
#include "ProphecyBreathingData.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "TwoBoneIK.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace ProphecyBreathing
{
namespace
{
using ProphecyBreathingData::Count;
using ProphecyBreathingData::Ticks;
using ProphecyBreathingData::Phases;
using ProphecyBreathingData::Samples;
struct FLayout
{
    TArray<FName> Names;
    TArray<int32> Parents;
    int32 Upper[Count],Legs[2][4];
    bool Valid=true;
};
struct FState
{
    EProphecyBreathingMode Mode=EProphecyBreathingMode::UpperAndPelvis;
    int32 Layout=INDEX_NONE;
    uint64 Start=0,Last=0,Previous=0;
    bool Active=false;
    float PelvisMultiplier=1.f,UpperBodyMultiplier=1.f;
    int32 Phase=0,SpeedStep=10;
};
TMap<TWeakObjectPtr<const AProphecyAgent>,FState> States;
TArray<FLayout> Layouts;
FDelegateHandle Cleanup;

void EnsureCleanup()
{
    if(Cleanup.IsValid())return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool){
        for(auto It=States.CreateIterator();It;++It)
            if(!It.Key().IsValid()||It.Key()->GetWorld()==World)It.RemoveCurrent();
        if(States.IsEmpty()){
            Layouts.Reset();FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset();
        }
    });
}
int32 LayoutFor(TConstArrayView<FName> Names,TConstArrayView<int32> Parents)
{
    for(int32 I=0;I<Layouts.Num();++I)
        if(Names.Num()==Layouts[I].Names.Num()&&FMemory::Memcmp(Names.GetData(),Layouts[I].Names.GetData(),Names.Num()*sizeof(FName))==0)return I;
    FLayout L;L.Names.Append(Names.GetData(),Names.Num());L.Parents.Append(Parents.GetData(),Parents.Num());
    for(int32 I=0;I<Count;++I){L.Upper[I]=Names.IndexOfByKey(FName(ProphecyBreathingData::Names[I]));L.Valid&=L.Upper[I]!=INDEX_NONE;}
    const FName Legs[2][4]={{TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l")},
                          {TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")}};
    for(int32 S=0;S<2;++S)for(int32 J=0;J<4;++J){L.Legs[S][J]=Names.IndexOfByKey(Legs[S][J]);L.Valid&=L.Legs[S][J]!=INDEX_NONE;}
    return Layouts.Add(MoveTemp(L));
}
FTransform Offset(const FTransform& Base,int32 From,int32 Tick,int32 Bone,float Multiplier=1.f)
{
    if(Multiplier==0.f)return Base;
    const auto* D=Samples[Tick][Bone];const auto* P=Samples[From][Bone];
    FQuat Delta=FQuat(D[3],D[4],D[5],D[6])*FQuat(-P[3],-P[4],-P[5],P[6]);
    if(Multiplier!=1.f){
        Delta.Normalize();if(Delta.W<0)Delta=Delta*-1.;
        FVector Axis;double Angle;Delta.ToAxisAndAngle(Axis,Angle);
        Delta=FQuat(Axis,Angle*Multiplier);
    }
    return FTransform((Delta*Base.GetRotation()).GetNormalized(),
        Base.GetLocation()+Multiplier*FVector(D[0]-P[0],D[1]-P[1],D[2]-P[2]),Base.GetScale3D());
}
struct FLeg
{
    FTransform HipLocal,Thigh,Knee,Foot;
    double Upper,Lower;
    FVector Hip(const FTransform& Pelvis)const{return Pelvis.TransformPosition(HipLocal.GetLocation());}
    bool Reaches(const FTransform& Pelvis)const{
        const double D2=FVector::DistSquared(Hip(Pelvis),Foot.GetLocation());
        return D2<=FMath::Square(Upper+Lower)+1.e-8 && D2>=FMath::Square(Upper-Lower)-1.e-8;
    }
};
void ApplySample(const FLayout& L,int32 From,int32 Tick,bool Pelvis,TArrayView<FTransform> Pose,TArrayView<FTransform> Locals={},float PelvisMultiplier=1.f,float UpperMultiplier=1.f)
{
    if(From==Tick)return;
    FTransform Local[Count];
    for(int32 I=0;I<Count;++I){
        const int32 B=L.Upper[I],P=ProphecyBreathingData::Parents[I];
        Local[I]=!Locals.IsEmpty()?Locals[B]:P<0?Pose[B]:Pose[B].GetRelativeTransform(Pose[L.Upper[P]]);
    }
    const FTransform OriginalPelvis=Pose[L.Upper[0]];
    if(Pelvis&&PelvisMultiplier!=0.f){
        FLeg Legs[2];
        for(int32 S=0;S<2;++S){auto& G=Legs[S];
            G.Thigh=Pose[L.Legs[S][0]];G.Knee=Pose[L.Legs[S][1]];G.Foot=Pose[L.Legs[S][2]];
            G.HipLocal=G.Thigh.GetRelativeTransform(OriginalPelvis);
            G.Upper=FVector::Distance(G.Thigh.GetLocation(),G.Knee.GetLocation());
            G.Lower=FVector::Distance(G.Knee.GetLocation(),G.Foot.GetLocation());
        }
        FTransform Target=Offset(Local[0],From,Tick,0,PelvisMultiplier);
        // A planted leg cannot become longer than its two segments. Only if
        // necessary, reduce this pelvis offset; never drag the feet or stretch.
        if(!Legs[0].Reaches(Target)||!Legs[1].Reaches(Target)){
            float Low=0,High=1;FTransform Candidate;
            for(int32 I=0;I<12;++I){const float A=(Low+High)*.5f;Candidate.Blend(OriginalPelvis,Target,A);
                if(Legs[0].Reaches(Candidate)&&Legs[1].Reaches(Candidate))Low=A;else High=A;
            }
            Target.Blend(OriginalPelvis,Target,Low);
        }
        Pose[L.Upper[0]]=Target;
        for(int32 S=0;S<2;++S){const auto& G=Legs[S];const FVector Hip=G.Hip(Target);
            FVector Knee,End;
            AnimationCore::SolveTwoBoneIK(Hip,G.Knee.GetLocation(),G.Foot.GetLocation(),
                G.Knee.GetLocation(),G.Foot.GetLocation(),Knee,End,G.Upper,G.Lower,false,1.,1.);
            auto& Thigh=Pose[L.Legs[S][0]];auto& Calf=Pose[L.Legs[S][1]];
            Thigh.SetLocation(Hip);
            Thigh.SetRotation((FQuat::FindBetweenNormals((G.Knee.GetLocation()-G.Thigh.GetLocation()).GetSafeNormal(),
                (Knee-Hip).GetSafeNormal())*G.Thigh.GetRotation()).GetNormalized());
            Calf.SetLocation(Knee);
            Calf.SetRotation((FQuat::FindBetweenNormals((G.Foot.GetLocation()-G.Knee.GetLocation()).GetSafeNormal(),
                (G.Foot.GetLocation()-Knee).GetSafeNormal())*G.Knee.GetRotation()).GetNormalized());
            // Foot/toe positions AND rotations remain exactly the NN's values.
            if(!Locals.IsEmpty())for(int32 J=0;J<4;++J){const int32 B=L.Legs[S][J];Locals[B]=Pose[B].GetRelativeTransform(Pose[L.Parents[B]]);}
        }
        if(!Locals.IsEmpty())Locals[L.Upper[0]]=Target;
    }
    for(int32 I=1;I<Count;++I){const int32 B=L.Upper[I];const FTransform Changed=Offset(Local[I],From,Tick,I,UpperMultiplier);
        Pose[B]=Changed*Pose[L.Upper[ProphecyBreathingData::Parents[I]]];
        if(!Locals.IsEmpty())Locals[B]=Changed;
    }
}
}

EProphecyBreathingMode Apply(const AProphecyAgent* A,uint64 Tick,bool Eligible,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TArrayView<FTransform> Current,TArrayView<FTransform> Local)
{
    auto* S=States.Find(A);
    if(!Eligible || (S&&(S->Mode==EProphecyBreathingMode::None ||
        (S->UpperBodyMultiplier==0.f&&(S->Mode==EProphecyBreathingMode::UpperOnly||S->PelvisMultiplier==0.f)))))
        {if(S)S->Active=false;return EProphecyBreathingMode::None;}
    if(!S){S=&States.Add(A);EnsureCleanup();}
    if(S->Layout==INDEX_NONE)S->Layout=LayoutFor(Names,Parents);
    const auto& L=Layouts[S->Layout];if(!L.Valid)return EProphecyBreathingMode::None;
    if(!S->Active||Tick<S->Last){S->Start=S->Previous=S->Last=Tick;S->Phase=0;S->Active=true;return EProphecyBreathingMode::None;}
    if(Tick==S->Last)return EProphecyBreathingMode::None;
    S->Previous=S->Last;S->Last=Tick;
    const int32 From=S->Phase;
    // All eight rates land exactly on the baked tenth-tick grid. Integer
    // lookup only: no runtime resampling, float clock or phase reset on edits.
    S->Phase=(From+int32((Tick-S->Previous)%Phases)*S->SpeedStep)%Phases;
    const bool Pelvis=S->Mode==EProphecyBreathingMode::UpperAndPelvis&&S->PelvisMultiplier!=0.f;
    // Current already contains the preceding accepted breathing pose through
    // NN history. Add only this interval; stopping never removes prior motion.
    ApplySample(L,From,S->Phase,Pelvis,Current,Local,S->PelvisMultiplier,S->UpperBodyMultiplier);
    return Pelvis?EProphecyBreathingMode::UpperAndPelvis:EProphecyBreathingMode::UpperOnly;
}
void Reset(const AProphecyAgent* A){if(auto* S=States.Find(A))S->Active=false;}
void Remove(const AProphecyAgent* A){States.Remove(A);}

#if !UE_BUILD_SHIPPING
static FAutoConsoleCommandWithWorldAndArgs SetMode(TEXT("Prophecy.Breathing.SetMode"),TEXT("Diagnostic: mode 0/1/2, optional actor name; PIE only."),
FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args,UWorld* W){
    if(!W||!W->IsGameWorld()||Args.IsEmpty()||(Args[0]!=TEXT("0")&&Args[0]!=TEXT("1")&&Args[0]!=TEXT("2")))return;
    const auto Mode=EProphecyBreathingMode(FCString::Atoi(*Args[0]));
    for(TActorIterator<AProphecyAgent> It(W);It;++It)
        if(Args.Num()<2||It->GetName()==Args[1])UProphecyBreathingLibrary::SetBreathingMode(*It,Mode);
}));
static FAutoConsoleCommandWithWorld Inspect(TEXT("Prophecy.Breathing.Inspect"),TEXT("Write breathing state; no mutation."),
FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* W){
    FString Text;
    for(const auto& Pair:States){const auto* A=Pair.Key.Get();const auto& S=Pair.Value;if(A&&A->GetWorld()==W)
        Text+=FString::Printf(TEXT("%s mode=%d active=%d tick=%llu period=%d phase=%d speed=%.1f\n"),*A->GetName(),int(S.Mode),S.Active,S.Active?(S.Last-S.Start)%Ticks:0,Ticks,S.Phase,S.SpeedStep*.1);}
    FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/Breathing-state.txt")));
}));
#endif
}

bool UProphecyBreathingLibrary::SetBreathingMode(AProphecyAgent* A,EProphecyBreathingMode Mode)
{
    if(!IsInGameThread()||!IsValid(A)||uint8(Mode)>uint8(EProphecyBreathingMode::UpperAndPelvis))return false;
    auto& S=ProphecyBreathing::States.FindOrAdd(A);
    if(S.Mode!=Mode){S.Mode=Mode;S.Active=false;}
    ProphecyBreathing::EnsureCleanup();return true;
}
EProphecyBreathingMode UProphecyBreathingLibrary::GetBreathingMode(AProphecyAgent* A)
{
    const auto* S=ProphecyBreathing::States.Find(A);return S?S->Mode:EProphecyBreathingMode::UpperAndPelvis;
}

bool UProphecyBreathingLibrary::SetBreathingMultipliers(AProphecyAgent* A,float PelvisMultiplier,float UpperBodyMultiplier)
{
    if(!IsInGameThread()||!IsValid(A)||!FMath::IsFinite(PelvisMultiplier)||!FMath::IsFinite(UpperBodyMultiplier))return false;
    auto& S=ProphecyBreathing::States.FindOrAdd(A);
    S.PelvisMultiplier=FMath::Max(0.f,PelvisMultiplier);S.UpperBodyMultiplier=FMath::Max(0.f,UpperBodyMultiplier);
    ProphecyBreathing::EnsureCleanup();return true;
}

float UProphecyBreathingLibrary::SetBreathingSpeedMultiplier(AProphecyAgent* A,float Multiplier)
{
    if(!IsInGameThread()||!IsValid(A)||!FMath::IsFinite(Multiplier))return 0.f;
    auto& S=ProphecyBreathing::States.FindOrAdd(A);
    S.SpeedStep=FMath::RoundToInt(FMath::Clamp(Multiplier,.3f,1.f)*10.f);
    ProphecyBreathing::EnsureCleanup();return S.SpeedStep*.1f;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Tests/ProphecyBreathingTests.inl"
#endif
