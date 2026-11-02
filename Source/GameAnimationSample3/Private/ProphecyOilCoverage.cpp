#include "ProphecyOilCoverage.h"
#include "ProphecyOil.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Components/DecalComponent.h"
#include "Engine/Texture2D.h"
#include "TextureResource.h"
#include "Engine/World.h"
#include "GameFramework/WorldSettings.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/StrongObjectPtr.h"
#include "Misc/App.h"
#include "EngineGlobals.h"

// A connected puddle owns one coverage mask, not one alpha layer per drop.
// Union is computed only while its footprint changes; settled fade is uniform.
// Body-local charts keep it attached to receivers without modifying their materials.
struct FOilCoverageGroup;
struct FProphecyOilCoverageStamp
{
    FVector Point,Normal;
    float Radius=0,Seed=0;
    uint64 Born=0;
    bool Landing=false;
    TWeakPtr<FOilCoverageGroup> Group;
};
namespace OilCoveragePrivate
{
constexpr int32 MaskSize=512;
constexpr float CellSize=128;
struct FCell
{
    int32 Slot;uint64 Generation;int32 Axis,U,V;
    bool operator==(const FCell& B)const{return Slot==B.Slot&&Generation==B.Generation&&Axis==B.Axis&&U==B.U&&V==B.V;}
    friend uint32 GetTypeHash(const FCell& K){return HashCombine(HashCombine(GetTypeHash(K.Slot),GetTypeHash(K.Generation)),HashCombine(GetTypeHash(K.Axis),HashCombine(GetTypeHash(K.U),GetTypeHash(K.V))));}
};
int32 Axis(const FVector& N){const FVector A=N.GetAbs();const int32 I=A.X>A.Y?(A.X>A.Z?0:2):(A.Y>A.Z?1:2);return I*2+(N[I]<0?1:0);}
FVector2D Project(const FVector& P,int32 A){const int32 I=A/2;return FVector2D(P[(I+1)%3],P[(I+2)%3]);}
struct FWorldCoverage
{
    uint64 Clock=0,LastFrame=MAX_uint64,Serial=0;
    TArray<TSharedPtr<FOilCoverageGroup>> Groups;
    TMap<FCell,TArray<TWeakPtr<FProphecyOilCoverageStamp>>> Cells;
};
TMap<TWeakObjectPtr<UWorld>,FWorldCoverage> Worlds;
}
struct FOilCoverageGroup
{
    FProphecyJoltBodyHandle Body;
    FVector Origin,Normal,U,V,Center;
    FQuat Rotation;
    FVector Extent;
    TArray<TSharedPtr<FProphecyOilCoverageStamp>> Stamps;
    TStrongObjectPtr<UMaterialInterface> CoatParent,TintParent;
    TStrongObjectPtr<UTexture2D> Mask;
    TStrongObjectPtr<UDecalComponent> Coat,Tint;
    uint64 LastLanding=0,Hold=0,Fade=0,GrowUntil=0;
#if !UE_BUILD_SHIPPING
    int32 Rebuilds=0;double RasterMs=0;
#endif
    float Strength=1,Applied=-1;
    bool Moving=false,Dirty=true;
    ~FOilCoverageGroup(){if(Coat.IsValid())Coat->DestroyComponent();if(Tint.IsValid())Tint->DestroyComponent();}
};
namespace OilCoveragePrivate
{
template<typename F> void VisitCells(const FProphecyJoltBodyHandle& Body,const FVector& Point,const FVector& Normal,float Radius,F Func)
{
    const int32 A=Axis(Normal);const FVector2D P=Project(Point,A);
    for(int32 Y=FMath::FloorToInt((P.Y-Radius)/CellSize);Y<=FMath::FloorToInt((P.Y+Radius)/CellSize);++Y)
    for(int32 X=FMath::FloorToInt((P.X-Radius)/CellSize);X<=FMath::FloorToInt((P.X+Radius)/CellSize);++X)Func(FCell{Body.Slot,Body.Generation,A,X,Y});
}
void Rasterize(const TArray<FVector2D,TInlineAllocator<32>>& Polygon,TArray<uint8>& Pixels)
{
    double Lo=MaskSize,Hi=0;for(const auto& P:Polygon){Lo=FMath::Min(Lo,P.Y);Hi=FMath::Max(Hi,P.Y);}
    for(int32 Y=FMath::Max(0,FMath::CeilToInt(Lo-.5));Y<=FMath::Min(MaskSize-1,FMath::FloorToInt(Hi-.5));++Y)
    {
        TArray<double,TInlineAllocator<32>> Crossings;const double Scan=Y+.5;
        for(int32 I=0;I<Polygon.Num();++I)
        {
            const auto A=Polygon[I],B=Polygon[(I+1)%Polygon.Num()];
            if((A.Y<=Scan&&B.Y>Scan)||(B.Y<=Scan&&A.Y>Scan))Crossings.Add(A.X+(Scan-A.Y)*(B.X-A.X)/(B.Y-A.Y));
        }
        Crossings.Sort();
        for(int32 I=0;I+1<Crossings.Num();I+=2)
        {
            const int32 X0=FMath::Max(0,FMath::CeilToInt(Crossings[I]-.5)),X1=FMath::Min(MaskSize-1,FMath::FloorToInt(Crossings[I+1]-.5));
            if(X1>=X0)FMemory::Memset(Pixels.GetData()+Y*MaskSize+X0,255,X1-X0+1);
        }
    }
}
void Rebuild(UWorld* World,FOilCoverageGroup& G,uint64 Clock)
{
#if !UE_BUILD_SHIPPING
    const double Begin=FPlatformTime::Seconds();++G.Rebuilds;
#endif
    FVector2D Lo(DBL_MAX,DBL_MAX),Hi(-DBL_MAX,-DBL_MAX);double DepthLo=DBL_MAX,DepthHi=-DBL_MAX;
    for(const auto& P:G.Stamps)
    {
        const FVector D=P->Point-G.Origin;const FVector2D C(FVector::DotProduct(D,G.U),FVector::DotProduct(D,G.V));
        Lo.X=FMath::Min(Lo.X,C.X-P->Radius);Lo.Y=FMath::Min(Lo.Y,C.Y-P->Radius);
        Hi.X=FMath::Max(Hi.X,C.X+P->Radius);Hi.Y=FMath::Max(Hi.Y,C.Y+P->Radius);
        const double Depth=FVector::DotProduct(D,G.Normal),Tilt=P->Radius*FMath::Sqrt(FMath::Max(0.,1.-FMath::Square(FVector::DotProduct(P->Normal,G.Normal))));
        DepthLo=FMath::Min(DepthLo,Depth-Tilt);DepthHi=FMath::Max(DepthHi,Depth+Tilt);
    }
    Lo-=FVector2D(1,1);Hi+=FVector2D(1,1);const FVector2D Size=Hi-Lo;
    G.Center=G.Origin+G.U*((Hi.X+Lo.X)*.5)+G.V*((Hi.Y+Lo.Y)*.5)+G.Normal*((DepthHi+DepthLo)*.5);
    G.Extent=FVector(8+(DepthHi-DepthLo)*.5,Size.X*.5,Size.Y*.5);
    TArray<uint8> Pixels;Pixels.SetNumZeroed(MaskSize*MaskSize);
    for(const auto& P:G.Stamps)
    {
        const float Spread=P->Landing?FMath::Lerp(.25f,1.f,FMath::Clamp(float(Clock-P->Born)/6.f,0.f,1.f)):1.f;
        const FQuat Q=(-P->Normal).Rotation().Quaternion();const FVector U=Q.GetAxisY(),V=Q.GetAxisZ();
        TArray<FVector2D,TInlineAllocator<32>> Polygon;
        for(int32 I=0;I<32;++I)
        {
            const double A=I*2*PI/32,Radius=P->Radius*Spread*(.94+.035*FMath::Sin(3*A+P->Seed)+.025*FMath::Sin(7*A+2*P->Seed)-.0175);
            const FVector D=P->Point+Radius*(U*FMath::Cos(A)+V*FMath::Sin(A))-G.Origin;
            Polygon.Add(FVector2D((FVector::DotProduct(D,G.U)-Lo.X)/Size.X*MaskSize,(FVector::DotProduct(D,G.V)-Lo.Y)/Size.Y*MaskSize));
        }
        Rasterize(Polygon,Pixels);
    }
    if(!G.Mask.IsValid())
    {
        G.Mask.Reset(UTexture2D::CreateTransient(MaskSize,MaskSize,PF_G8));G.Mask->SRGB=false;G.Mask->Filter=TF_Bilinear;
        G.Mask->AddressX=TA_Clamp;G.Mask->AddressY=TA_Clamp;G.Mask->NeverStream=true;
        auto& Bulk=G.Mask->GetPlatformData()->Mips[0].BulkData;
        void* Initial=Bulk.Lock(LOCK_READ_WRITE);FMemory::Memcpy(Initial,Pixels.GetData(),Pixels.Num());Bulk.Unlock();
        G.Mask->UpdateResource();
    }
    else if(FApp::CanEverRender())
    {
        auto* Bytes=new uint8[MaskSize*MaskSize];FMemory::Memcpy(Bytes,Pixels.GetData(),Pixels.Num());
        auto* Region=new FUpdateTextureRegion2D(0,0,0,0,MaskSize,MaskSize);
        G.Mask->UpdateTextureRegions(0,1,Region,MaskSize,1,Bytes,[](uint8* Data,const FUpdateTextureRegion2D* R){delete[] Data;delete R;});
    }
    auto Make=[&](TStrongObjectPtr<UDecalComponent>& Decal,UMaterialInterface* Parent)
    {
        if(!Parent)return;
        if(!Decal.IsValid())
        {
            Decal.Reset(NewObject<UDecalComponent>(World->GetWorldSettings()));Decal->ComponentTags.Add(TEXT("ProphecyOilCoverage"));
            Decal->SetDecalMaterial(Parent);Decal->SetFadeScreenSize(.002f);Decal->RegisterComponent();Decal->CreateDynamicMaterialInstance();
        }
        Decal->DecalSize=G.Extent;
        if(auto* MID=Cast<UMaterialInstanceDynamic>(Decal->GetDecalMaterial())){MID->SetTextureParameterValue(TEXT("OilCoverage"),G.Mask.Get());MID->SetScalarParameterValue(TEXT("OilAmount"),G.Strength);}
    };
    Make(G.Coat,G.CoatParent.Get());Make(G.Tint,G.TintParent.Get());G.Dirty=false;
#if !UE_BUILD_SHIPPING
    G.RasterMs+=(FPlatformTime::Seconds()-Begin)*1000;
#endif
}
}
namespace ProphecyOilCoverage
{
using namespace OilCoveragePrivate;
TSharedPtr<FProphecyOilCoverageStamp> Add(UWorld* World,const FProphecyJoltBodyHandle& Body,const FVector& Point,const FVector& Normal,float Radius,bool Moving,bool Landing,const FProphecyOilSettings& Settings)
{
    auto& W=Worlds.FindOrAdd(World);TArray<TSharedPtr<FOilCoverageGroup>> Joining;TSet<const FProphecyOilCoverageStamp*> Seen;
    VisitCells(Body,Point,Normal,Radius,[&](const FCell& Cell)
    {
        if(auto* Entries=W.Cells.Find(Cell))for(const auto& Entry:*Entries)if(auto P=Entry.Pin())if(!Seen.Contains(P.Get()))
        {
            Seen.Add(P.Get());auto G=P->Group.Pin();if(!G || G->Strength<=0 || G->CoatParent.Get()!=Settings.DecalMaterial || G->TintParent.Get()!=Settings.TintMaterial)continue;
            const FVector D=Point-P->Point;
            if(FVector::DotProduct(G->Normal,Normal)>.95 && FMath::Abs(FVector::DotProduct(D,Normal))<=8
                && FMath::Abs(FVector::DotProduct(D,P->Normal))<=8 && D.SizeSquared()<=FMath::Square(Radius+P->Radius))Joining.AddUnique(G);
        }
    });
    TSharedPtr<FOilCoverageGroup> G;
    if(Joining.IsEmpty())
    {
        G=MakeShared<FOilCoverageGroup>();G->Body=Body;G->Origin=Point;G->Normal=Normal;G->Rotation=(-Normal).Rotation().Quaternion();
        G->U=G->Rotation.GetAxisY();G->V=G->Rotation.GetAxisZ();G->Moving=Moving;
        G->CoatParent.Reset(Settings.DecalMaterial);G->TintParent.Reset(Settings.TintMaterial);W.Groups.Add(G);
    }
    else
    {
        G=Joining[0];for(int32 I=1;I<Joining.Num();++I)
        {
            for(auto& P:Joining[I]->Stamps){P->Group=G;G->Stamps.Add(P);}
            G->Hold=FMath::Max(G->Hold,Joining[I]->Hold);G->Fade=FMath::Max(G->Fade,Joining[I]->Fade);
            G->GrowUntil=FMath::Max(G->GrowUntil,Joining[I]->GrowUntil);W.Groups.Remove(Joining[I]);
        }
    }
    auto P=MakeShared<FProphecyOilCoverageStamp>();P->Point=Point;P->Normal=Normal;P->Radius=Radius;
    P->Born=W.Clock;P->Landing=Landing;P->Seed=++W.Serial*2.399963f;P->Group=G;G->Stamps.Add(P);
    G->LastLanding=W.Clock;G->Hold=FMath::Max(G->Hold,uint64(FMath::CeilToInt(Settings.HoldDuration*60.)));
    G->Fade=FMath::Max(G->Fade,uint64(FMath::CeilToInt(Settings.FadeDuration*60.)));G->Strength=1;G->Dirty=true;
    if(Landing)G->GrowUntil=FMath::Max(G->GrowUntil,W.Clock+6);
    VisitCells(Body,Point,Normal,Radius,[&](const FCell& Cell){W.Cells.FindOrAdd(Cell).Add(P);});return P;
}
void Tick(UWorld* World)
{
    auto* W=Worlds.Find(World);if(!W || W->LastFrame==GFrameCounter || World->IsPaused())return;W->LastFrame=GFrameCounter;++W->Clock;
    auto* Native=World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    for(const auto& G:W->Groups)
    {
        const uint64 Age=W->Clock-G->LastLanding;G->Strength=Age<G->Hold?1.f:(G->Fade?1.f-FMath::Clamp(float(Age-G->Hold)/G->Fade,0.f,1.f):0.f);
        if(!Native || !Native->OwnsBody(G->Body)){G->Strength=0;continue;}
        const bool Growing=W->Clock<=G->GrowUntil;
        const bool Changed=G->Dirty||Growing;
        if(Changed && G->Strength>0)Rebuild(World,*G,W->Clock);
        if(G->Strength!=G->Applied)
        {
            for(auto* D:{G->Coat.Get(),G->Tint.Get()})if(D)if(auto* M=Cast<UMaterialInstanceDynamic>(D->GetDecalMaterial()))M->SetScalarParameterValue(TEXT("OilAmount"),G->Strength);
            G->Applied=G->Strength;
        }
        if(G->Moving||Changed)
        {
            FProphecyJoltBodyState B;if(!Native->ReadBody(G->Body,B).IsSuccess()){G->Strength=0;continue;}
            const FTransform T(B.Rotation,B.PositionCm);
            for(auto* D:{G->Coat.Get(),G->Tint.Get()})if(D)D->SetWorldLocationAndRotation(T.TransformPosition(G->Center),B.Rotation*G->Rotation);
        }
    }
}
float Amount(const TSharedPtr<FProphecyOilCoverageStamp>& P){if(P)if(auto G=P->Group.Pin())return G->Strength;return 0;}
#if !UE_BUILD_SHIPPING
FStats Stats(UWorld* World)
{
    FStats S;if(auto* W=Worlds.Find(World))for(const auto& G:W->Groups)
    {++S.Groups;S.Stamps+=G->Stamps.Num();S.Rebuilds+=G->Rebuilds;S.RasterMs+=G->RasterMs;}return S;
}
#endif
void Remove(UWorld* World,const TSharedPtr<FProphecyOilCoverageStamp>& P)
{
    auto* W=Worlds.Find(World);auto G=P?P->Group.Pin():nullptr;if(!W||!G)return;
    VisitCells(G->Body,P->Point,P->Normal,P->Radius,[&](const FCell& C){if(auto* Entries=W->Cells.Find(C)){Entries->RemoveAll([&](const auto& E){auto S=E.Pin();return !S||S==P;});if(Entries->IsEmpty())W->Cells.Remove(C);}});
    G->Stamps.Remove(P);P->Group.Reset();G->Dirty=true;if(G->Stamps.IsEmpty())W->Groups.Remove(G);
    if(W->Groups.IsEmpty())Worlds.Remove(World);
}
}
