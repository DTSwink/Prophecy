#include "BloodMergeScene.h"
#include "Components/DecalComponent.h"
#include "Components/SceneComponent.h"
#include "DrawDebugHelpers.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "Modules/ModuleManager.h"
#include "HAL/PlatformTime.h"

IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, BloodDecalLab, "BloodDecalLab");

namespace
{
int32 FloorDiv32(int32 V) { return V>=0 ? V/32 : int32((int64(V)-31)/32); }
TArray<FIntPoint> ShapeCells(FName Name)
{
    TArray<FIntPoint> Cells;
    // Deliberately start at an odd offset: the old irreversible square merges jam.
    if(Name=="filled")
        Cells.Append({{7,7},{8,7},{7,8},{8,8}});
    FRandomStream R(31415);
    for(int Y=0;Y<16;++Y) for(int X=0;X<16;++X)
    {
        bool Include=true;
        if(Name=="hole") Include=!(X>=5 && X<11 && Y>=5 && Y<11);
        if(Name=="splash") Include=(FMath::Square(X-8)+FMath::Square(Y-8)<R.RandRange(25,64));
        if(Name=="checker") Include=((X+Y)%2==0);
        if(Name=="strip") Include=(Y<2);
        if(Include) Cells.AddUnique({X,Y});
    }
    return Cells;
}
}

ABloodMergeScene::ABloodMergeScene()
{
    SetRootComponent(CreateDefaultSubobject<USceneComponent>("Root"));
    PrimaryActorTick.bCanEverTick=true;
    PrimaryActorTick.bStartWithTickEnabled=false;
    Scratch.reserve(512);
}

void ABloodMergeScene::BeginPlay()
{
    Super::BeginPlay();
    Populate(Pattern);
    SetActorTickEnabled(Spray || ShowBounds || Dirty.Num()>DirtyHead);
}

bool ABloodMergeScene::AddCell(int32 X,int32 Y)
{
    const FIntPoint Key(FloorDiv32(X),FloorDiv32(Y));
    FBloodLabRegion* Region=Regions.Find(Key);
    if(!Region)
    {
        if(Regions.Num()>=FMath::Max(1,MaxRegions)) { ++RejectedCells;return false; }
        Region=&Regions.Add(Key);
    }
    const int32 LX=X-Key.X*32, LY=Y-Key.Y*32;
    const uint32 Bit=uint32(1)<<LX;
    if(Region->Mask[LY]&Bit) return false;
    Region->Mask[LY]|=Bit;
    CapacityBlocked=false;
    ++OccupiedCells;
    if(!Region->Dirty) { Region->Dirty=true;Dirty.Add(Key); }
    SetActorTickEnabled(true);
    return true;
}

int32 ABloodMergeScene::AddStain(FVector WorldPosition,float Radius)
{
    if(WorldPosition.ContainsNaN() || !FMath::IsFinite(Radius) || Radius<0 || CellSize<=0) return 0;
    const FVector P=GetActorTransform().InverseTransformPosition(WorldPosition);
    // This isolated lab has one explicit planar receiver per grid actor.
    if(FMath::Abs(P.Z)>1.f) return 0;
    const int32 CX=FMath::FloorToInt(P.X/CellSize), CY=FMath::FloorToInt(P.Y/CellSize);
    const int32 Reach=FMath::Clamp(FMath::CeilToInt((Radius+CellSize*.5f)/CellSize),0,16);
    const double Limit=FMath::Square(Radius+CellSize*.7072f);
    int32 Count=0;
    for(int Y=CY-Reach;Y<=CY+Reach;++Y) for(int X=CX-Reach;X<=CX+Reach;++X)
    {
        if(Radius==0 && (X!=CX || Y!=CY)) continue;
        if(Radius>0 && FMath::Square((X+.5)*CellSize-P.X)+FMath::Square((Y+.5)*CellSize-P.Y)>Limit) continue;
        Count+=AddCell(X,Y)?1:0;
    }
    return Count;
}

UDecalComponent* ABloodMergeScene::Acquire()
{
    if(SpareDecals.Num()) return SpareDecals.Pop(EAllowShrinking::No);
    return CreateDecal();
}

UDecalComponent* ABloodMergeScene::CreateDecal()
{
    if(OwnedDecals.Num()>=FMath::Max(1,MaxDecals)) return nullptr;
    UDecalComponent* D=NewObject<UDecalComponent>(this);
    D->SetMobility(EComponentMobility::Movable);
    D->SetDecalMaterial(DecalMaterial);
    D->SetFadeScreenSize(0.f);
    D->SetVisibility(false);
    D->SetupAttachment(GetRootComponent());
    D->RegisterComponent();
    OwnedDecals.Add(D);
    ++CreatedComponents;
    return D;
}

void ABloodMergeScene::Place(UDecalComponent* D,float X,float Y,float W,float H,bool LegacySize)
{
    // Unreal DecalSize is HALF-extents. Local X projects; Y/Z cover receiver.
    const float Factor=LegacySize?1.f:.5f;
    // At -90 pitch, decal local Y is world Y and local Z is world X.
    const FVector Size(Depth*.5f,H*CellSize*Padding*Factor,W*CellSize*Padding*Factor);
    const FVector Location((X+W*.5f)*CellSize,(Y+H*.5f)*CellSize,Depth*.5f-1.f);
    const FRotator Rotation(-90,0,0);
    if(D->IsVisible() && D->DecalSize==Size && D->GetRelativeLocation()==Location && D->GetRelativeRotation().Equals(Rotation)) return;
    D->DecalSize=Size;
    D->SetRelativeLocationAndRotation(Location,Rotation);
    D->SetVisibility(true);
    D->MarkRenderStateDirty();
}

bool ABloodMergeScene::Rebuild(const FIntPoint& Key,FBloodLabRegion& R,double Deadline,int32& NewThisUpdate)
{
    BloodRect::Mesh(R.Mask,Scratch);
    if(ActiveDecals-R.Decals.Num()+int32(Scratch.size())>MaxDecals)
    {
        CapacityBlocked=true;CapacityLimitAtBlock=MaxDecals;return false;
    }
    // Registration dominates cold sparse patches. Prepare a hidden pool over
    // multiple updates; keep the previous complete footprint until it is ready.
    const int32 Extra=FMath::Max(0,int32(Scratch.size())-R.Decals.Num());
    while(SpareDecals.Num()<Extra)
    {
        if(NewThisUpdate>=FMath::Max(1,MaxNewDecalsPerUpdate) ||
            (NewThisUpdate>0 && FPlatformTime::Seconds()>=Deadline)) return false;
        UDecalComponent* D=CreateDecal();
        if(!D) {CapacityBlocked=true;CapacityLimitAtBlock=MaxDecals;return false;}
        SpareDecals.Add(D);++NewThisUpdate;
    }
    if(NewThisUpdate>0 && FPlatformTime::Seconds()>=Deadline) return false;
    while(R.Decals.Num()>int32(Scratch.size()))
    {
        UDecalComponent* D=R.Decals.Pop(EAllowShrinking::No);
        D->SetVisibility(false);SpareDecals.Add(D);--ActiveDecals;
    }
    while(R.Decals.Num()<int32(Scratch.size()))
    {
        UDecalComponent* D=Acquire();
        if(!D) return false;
        R.Decals.Add(D);++ActiveDecals;
    }
    for(int I=0;I<int32(Scratch.size());++I)
    {
        const auto& Q=Scratch[I];
        Place(R.Decals[I],Key.X*32+Q.X,Key.Y*32+Q.Y,Q.W,Q.H);
    }
    ++Rebuilds;
    return true;
}

void ABloodMergeScene::ProcessChanges()
{
    if(CapacityBlocked && CapacityLimitAtBlock==MaxDecals) { LastUpdateMs=0;return; }
    CapacityBlocked=false;
    const double Start=FPlatformTime::Seconds();
    const double Deadline=Start+FMath::Max(.01f,UpdateBudgetMs)*.001;
    int32 NewThisUpdate=0;
    int Count=0;
    while(DirtyHead<Dirty.Num() && Count<FMath::Max(1,MaxRegionsPerUpdate))
    {
        if(Count && (FPlatformTime::Seconds()-Start)*1000>=UpdateBudgetMs) break;
        const FIntPoint Key=Dirty[DirtyHead++];
        FBloodLabRegion& R=Regions.FindChecked(Key);
        // On capacity failure leave the region queued, without allocating more components.
        if(!Rebuild(Key,R,Deadline,NewThisUpdate))
        {
            --DirtyHead;
            break;
        }
        R.Dirty=false;++Count;
    }
    if(DirtyHead==Dirty.Num()) { Dirty.Reset();DirtyHead=0; }
    LastUpdateMs=float((FPlatformTime::Seconds()-Start)*1000);
    if(!Spray && !ShowBounds && (Dirty.Num()==0 || CapacityBlocked)) SetActorTickEnabled(false);
}

void ABloodMergeScene::DrawBounds()
{
    for(const TObjectPtr<UDecalComponent>& D:OwnedDecals) if(IsValid(D) && D->IsVisible())
    {
        FVector Center=D->GetComponentLocation();
        Center.Z=GetActorLocation().Z+2.f;
        FVector Extent=D->DecalSize;
        Extent.X=1.f;
        DrawDebugBox(GetWorld(),Center,Extent,D->GetComponentQuat(),FColor::Cyan,false,0,0,.7f);
    }
}

void ABloodMergeScene::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if(Spray)
    {
        // Authored game time follows the project's 60-tick convention.
        SprayClock+=1.f/60.f;SprayAngle+=.75f;
        if(SprayClock>=.05f)
        {
            SprayClock=0;
            for(int I=0;I<8;++I)
            {
                const float A=FMath::DegreesToRadians(SprayAngle+Random.FRandRange(-20,20));
                const float R=Random.FRandRange(15,100);
                AddStain(GetActorTransform().TransformPosition(FVector(100+R*FMath::Cos(A),100+R*FMath::Sin(A),0)),5);
            }
        }
    }
    if(Dirty.Num()>DirtyHead) ProcessChanges();
    if(ShowBounds) DrawBounds();
}

void ABloodMergeScene::Clear()
{
    for(auto& D:OwnedDecals) if(IsValid(D)) D->DestroyComponent();
    OwnedDecals.Reset();SpareDecals.Reset();Regions.Reset();Dirty.Reset();OldTiles.Reset();
    DirtyHead=0;ActiveDecals=0;OccupiedCells=0;Rebuilds=0;CreatedComponents=0;RejectedCells=0;
    CapacityBlocked=false;
    SetActorTickEnabled(Spray || ShowBounds);
}

void ABloodMergeScene::LegacyPopulate(FName Shape)
{
    // Same four equal square merge rule, settled after each addition.
    // Behavioral baseline only; not a timing surrogate for the production code.
    for(const FIntPoint& P:ShapeCells(Shape))
    {
        OldTiles.Add({P.X,P.Y,0});
        bool Again=true;
        while(Again)
        {
            Again=false;
            for(int I=0;I<OldTiles.Num() && !Again;++I)
            {
                const FIntVector T=OldTiles[I];const int S=1<<T.Z;
                for(int DY=0;DY<2 && !Again;++DY) for(int DX=0;DX<2 && !Again;++DX)
                {
                    const FIntVector Parent(T.X-DX*S,T.Y-DY*S,T.Z+1);
                    TArray<FIntVector> ChildSquares;
                    for(int Y=0;Y<2;++Y) for(int X=0;X<2;++X) ChildSquares.Add({Parent.X+X*S,Parent.Y+Y*S,T.Z});
                    bool All=true;for(const auto& C:ChildSquares) All&=OldTiles.Contains(C);
                    if(All)
                    {
                        for(const auto& C:ChildSquares) OldTiles.RemoveSingleSwap(C,EAllowShrinking::No);
                        OldTiles.Add(Parent);Again=true;
                    }
                }
            }
        }
    }
    OccupiedCells=ShapeCells(Shape).Num();
    for(const auto& T:OldTiles)
    {
        UDecalComponent* D=Acquire();
        if(D) {Place(D,T.X,T.Y,1<<T.Z,1<<T.Z,true);++ActiveDecals;}
    }
}

void ABloodMergeScene::Populate(FName Shape)
{
    Clear();Pattern=Shape;
    if(LegacyComparison) {LegacyPopulate(Shape);return;}
    for(const FIntPoint& P:ShapeCells(Shape)) AddCell(P.X,P.Y);
    // Fixture initialization intentionally drains; normal Tick processes once.
    while(HasPendingChanges()) ProcessChanges();
}

FString ABloodMergeScene::Validate()
{
    FRandomStream R(9217);int Failures=0;int Cases=0;
    std::vector<BloodRect::Rect> Out;Out.reserve(512);
    for(int Trial=0;Trial<4000;++Trial)
    {
        BloodRect::Mask M{};
        const int Threshold=Trial%101;
        for(int Y=0;Y<32;++Y) for(int X=0;X<32;++X)
            if(R.RandRange(0,99)<Threshold) M[Y]|=uint32(1)<<X;
        BloodRect::Mesh(M,Out);Failures+=!BloodRect::Exact(M,Out);++Cases;
    }
    int FilledCount=0,HoleCount=0,CheckerCount=0;
    for(FName Name:{FName("filled"),FName("hole"),FName("checker"),FName("strip"),FName("splash")})
    {
        BloodRect::Mask M{};for(auto P:ShapeCells(Name)) M[P.Y]|=uint32(1)<<P.X;
        BloodRect::Mesh(M,Out);Failures+=!BloodRect::Exact(M,Out);++Cases;
        if(Name=="filled") FilledCount=int(Out.size());
        if(Name=="hole") HoleCount=int(Out.size());
        if(Name=="checker") CheckerCount=int(Out.size());
    }
    Failures+=(FilledCount!=1 || HoleCount!=4 || CheckerCount!=128);
    for(int X=-100;X<100;++X) {int C=FloorDiv32(X),L=X-C*32;Failures+=(L<0 || L>=32 || C*32+L!=X);}
    return FString::Printf(TEXT("{\"cases\":%d,\"failures\":%d,\"filled_rects\":%d,\"ring_rects\":%d,\"checker_rects\":%d}"),Cases,Failures,FilledCount,HoleCount,CheckerCount);
}

FString ABloodMergeScene::Benchmark()
{
    FRandomStream R(6291);
    std::vector<BloodRect::Mask> Input(256);
    for(auto& M:Input) for(auto& Row:M) Row=uint32(R.GetUnsignedInt());
    std::vector<BloodRect::Rect> Out;Out.reserve(512);
    int64 Sum=0;
    const double Start=FPlatformTime::Seconds();
    for(int I=0;I<20000;++I) {BloodRect::Mesh(Input[I%256],Out);Sum+=Out.size();}
    const double Us=(FPlatformTime::Seconds()-Start)*1e6/20000;
    return FString::Printf(TEXT("{\"kernel_us_per_32x32_region\":%.4f,\"iterations\":20000,\"checksum\":%lld,\"scope\":\"CPU partition only; excludes Unreal components and GPU\"}"),Us,Sum);
}
