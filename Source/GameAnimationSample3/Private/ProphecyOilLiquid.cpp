#include "ProphecyOilLiquid.h"
#include "ProphecyOil.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
// Optical silhouette, independent of physics. Smooth the lower meniscus/body
// fillet and circumference; the free surface remains genuinely flat.
constexpr int32 LiquidSides=48;
const FVector2D LiquidProfile[]={{.7,3.6},{.85,4.04},{1.1,4.47},{1.4,4.73},{1.7,4.85},
    {18,4.85},{19.2,4.65},{20.4,4.15},{21.2,3.6},{22.5,2.25},{24.5,1.8}};
// Clip one triangle to the liquid half-space; four vertices maximum, no allocation.
int32 Clip(const FVector* P,const FVector& N,double H,FVector* Q)
{
    int32 Count=0;
    for(int32 I=0;I<3;++I)
    {
        const FVector A=P[I],B=P[(I+1)%3];const double DA=FVector::DotProduct(N,A)-H,DB=FVector::DotProduct(N,B)-H;
        if(DA<=0)Q[Count++]=A;
        if((DA<0 && DB>0)||(DA>0 && DB<0))Q[Count++]=A+(B-A)*(DA/(DA-DB));
    }
    return Count;
}
double Volume(const TArray<FVector>& V,const TArray<int32>& T,const FVector& N,double H)
{
    // Tetrahedra originate on the cutting plane, so the cap's contribution is zero.
    const FVector Origin=N*H;double Sum=0;
    for(int32 I=0;I<T.Num();I+=3)
    {
        FVector P[3]={V[T[I]],V[T[I+1]],V[T[I+2]]},Q[4];const int32 Count=Clip(P,N,H,Q);
        for(int32 K=1;K+1<Count;++K)Sum+=FVector::DotProduct(Q[0]-Origin,FVector::CrossProduct(Q[K]-Origin,Q[K+1]-Origin));
    }
    return FMath::Abs(Sum)/6.;
}
}
UProphecyOilLiquid::UProphecyOilLiquid(const FObjectInitializer& ObjectInitializer):Super(ObjectInitializer)
{
    FillAmount=.85f; // Upright surface at the shoulder, about18.4cm above the base.
    PrimaryComponentTick.bCanEverTick=true;PrimaryComponentTick.bStartWithTickEnabled=false;
    PrimaryComponentTick.TickGroup=TG_PostUpdateWork;
    SetCollisionEnabled(ECollisionEnabled::NoCollision);SetGenerateOverlapEvents(false);SetCanEverAffectNavigation(false);
    CastShadow=false;bUseAsyncCooking=false;bUseComplexAsSimpleCollision=false;
    SetTranslucentSortPriority(-1); // The surrounding glass draws over its contents.
    // Native subobject has no editable Blueprint variable/template. Setting its
    // Blueprint CDO alone is lost on compilation; provide the durable default here.
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> DefaultLiquid(
        TEXT("/Game/_mygame/OilBottle/Materials/M_OilBottleLiquid.M_OilBottleLiquid"));
    if(DefaultLiquid.Succeeded())LiquidMaterial=DefaultLiquid.Object;
}
void UProphecyOilLiquid::BuildCavity()
{
    if(!Cavity.IsEmpty())return;
    // Inscribed low-poly cavity for the licensed bottle, cm, below the seated cork.
    // Narrower than the baked inner glass at every ring; never a separate physics body.
    const auto& Profile=LiquidProfile;
    constexpr int32 Sides=LiquidSides,Rings=UE_ARRAY_COUNT(LiquidProfile);
    for(auto P:Profile)for(int32 J=0;J<Sides;++J){const double A=J*2*PI/Sides;Cavity.Add(FVector(P.Y*FMath::Cos(A),P.Y*FMath::Sin(A),P.X));}
    for(int32 R=0;R<Rings-1;++R)for(int32 J=0;J<Sides;++J)
    {
        const int32 A=R*Sides+J,B=R*Sides+(J+1)%Sides,C=A+Sides,D=B+Sides;
        Faces.Append({A,B,C,B,D,C});
    }
    const int32 Bottom=Cavity.Add(FVector(0,0,Profile[0].X)),Top=Cavity.Add(FVector(0,0,Profile[Rings-1].X));
    for(int32 J=0;J<Sides;++J)Faces.Append({Bottom,(J+1)%Sides,J,Top,(Rings-1)*Sides+J,(Rings-1)*Sides+(J+1)%Sides});
    FullVolume=Volume(Cavity,Faces,FVector::UpVector,26);
    // Fixed topology: up to two clipped side triangles plus one cap triangle per source face.
    const int32 Capacity=Faces.Num()*3;
    Vertices.SetNumZeroed(Capacity);Normals.Init(FVector::UpVector,Capacity);UV.SetNumZeroed(Capacity);
    Colors.Init(FLinearColor::White,Capacity);Triangles.SetNumUninitialized(Capacity);
    // Clipping/volume math uses RH orientation; UE raster winding is opposite.
    // Reverse only the render indices, retaining the outward lighting normals.
    for(int32 I=0;I<Capacity;I+=3){Triangles[I]=I+1;Triangles[I+1]=I;Triangles[I+2]=I+2;}
}
void UProphecyOilLiquid::RefreshLiquid()
{
    BuildCavity();
    auto* Bottle=Cast<AProphecyOilBottle>(GetOwner());
    SetMaterial(0,LiquidMaterial?LiquidMaterial.Get():(Bottle?Bottle->Oil.DropletMaterial.Get():nullptr));
    bReady=GetMaterial(0)!=nullptr && FillAmount>0;
    SetVisibility(bReady);DrawnFill=-1;
    if(bReady)UpdateSurface();
    SetComponentTickEnabled(bReady && GetWorld() && GetWorld()->IsGameWorld());
}
void UProphecyOilLiquid::OnRegister()
{
    Super::OnRegister();Spring=GetComponentTransform().InverseTransformVector(FVector::UpVector).GetSafeNormal();RefreshLiquid();
}
void UProphecyOilLiquid::BeginPlay()
{
    Super::BeginPlay();bSampled=false;StillFrames=0;RefreshLiquid();
}
void UProphecyOilLiquid::OnUpdateTransform(EUpdateTransformFlags Flags,ETeleportType Teleport)
{
    Super::OnUpdateTransform(Flags,Teleport);
    if(bReady && FillAmount>0 && IsVisible() && HasBegunPlay() && !GetComponentTransform().Equals(SampleTransform,.0001))
    {
        if(!IsComponentTickEnabled())bSampled=false;
        SetComponentTickEnabled(true);StillFrames=0;
    }
}
void UProphecyOilLiquid::TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Function)
{
    Super::TickComponent(Delta,Type,Function);
    if(Delta<=0 || !GetWorld() || GetWorld()->IsPaused())return;
    if(!bReady || FillAmount<=0 || !IsVisible()){SetComponentTickEnabled(false);return;}
    constexpr double Dt=1./60.;
    const FTransform T=GetComponentTransform();const FVector P=T.GetLocation();
    const FVector Velocity=bSampled?(P-PreviousPosition)/Dt:FVector::ZeroVector;
    FVector Acceleration=bSampled?(Velocity-PreviousVelocity)/Dt:FVector::ZeroVector;
    // Limit impact/teleport impulses; uniform translation and angular changes remain smooth.
    Acceleration.Z=0;Acceleration=(Acceleration/980.).GetClampedToMaxSize(.7);
    const FVector Target=T.InverseTransformVector((FVector::UpVector+Acceleration*FMath::Clamp(SloshStrength,0.f,2.f)).GetSafeNormal()).GetSafeNormal();
    const double Damping=FMath::Clamp(SloshDamping,.1f,2.f);
    // Two tiny fixed substeps keep the cosmetic spring stable at all supported damping values.
    for(int32 I=0;I<2;++I)
    {SpringVelocity+=((Target-Spring)*100.-SpringVelocity*(20.*Damping))*(Dt*.5);Spring+=SpringVelocity*(Dt*.5);}
    if(Spring.IsNearlyZero())Spring=Target;
    const FVector N=Spring.GetSafeNormal();
    if(!N.Equals(DrawnNormal,.001) || !FMath::IsNearlyEqual(FillAmount,DrawnFill))UpdateSurface();
    const bool Quiet=(P-PreviousPosition).SizeSquared()<1.e-8 && T.GetRotation().AngularDistance(SampleTransform.GetRotation())<1.e-5
        && (Target-Spring).SizeSquared()<1.e-7 && SpringVelocity.SizeSquared()<1.e-6;
    StillFrames=Quiet?StillFrames+1:0;
    PreviousPosition=P;PreviousVelocity=Velocity;SampleTransform=T;bSampled=true;
    if(StillFrames>=12){Spring=Target;SpringVelocity=FVector::ZeroVector;UpdateSurface();SetComponentTickEnabled(false);}
}
void UProphecyOilLiquid::UpdateSurface()
{
    const double Start=FPlatformTime::Seconds();
    const FVector N=Spring.GetSafeNormal(UE_SMALL_NUMBER,FVector::UpVector);SurfaceNormal=N;
    const double Fill=FMath::Clamp(FillAmount,0.f,1.f),Target=FullVolume*Fill;
    if(HeightFill!=FillAmount)
    {
        auto HeightFor=[&](double Fraction)
        {
            double A=.7,B=24.5;
            for(int32 I=0;I<18;++I){const double H=(A+B)*.5;if(Volume(Cavity,Faces,FVector::UpVector,H)<FullVolume*Fraction)A=H;else B=H;}
            return (A+B)*.5;
        };
        UprightHeight=HeightFor(Fill);InvertedHeight=HeightFor(1.-Fill);HeightFill=FillAmount;
    }
    double Low=DBL_MAX,High=-DBL_MAX;
    for(const FVector& P:Cavity){const double D=FVector::DotProduct(N,P);Low=FMath::Min(Low,D);High=FMath::Max(High,D);}
    if(Fill>=1)Low=High;
    else if(Fill<=0)High=Low;
    else
    {
        const double Mid=N.Z>=0?UprightHeight:InvertedHeight;
        const double Reach=4.85*FMath::Sqrt(FMath::Max(0.,1.-N.Z*N.Z))/FMath::Max(.00001,FMath::Abs(N.Z));
        // Exact fast path: a tilted plane through a symmetric cylindrical section
        // preserves volume about its center. Only extreme tilts entering the shoulder
        // or base need a bounded volume solve. Normal handling is one clipped draw.
        if(Mid-Reach>=1.7 && Mid+Reach<=18)Low=High=N.Z*Mid;
        else for(int32 I=0;I<12;++I){const double H=(Low+High)*.5;if(Volume(Cavity,Faces,N,H)<Target)Low=H;else High=H;}
    }
    const double H=(Low+High)*.5;
    VolumeError=FMath::Abs(Volume(Cavity,Faces,N,H)-Target)/FullVolume;
    FVector Center=FVector::ZeroVector;int32 Cuts=0;
    // Average cross-section endpoints gives a stable fan center for this star-shaped bottle cavity.
    for(int32 I=0;I<Faces.Num();I+=3)for(int32 J=0;J<3;++J)
    {
        const FVector A=Cavity[Faces[I+J]],B=Cavity[Faces[I+(J+1)%3]];
        const double DA=FVector::DotProduct(N,A)-H,DB=FVector::DotProduct(N,B)-H;
        if((DA<0 && DB>0)||(DA>0 && DB<0)){Center+=A+(B-A)*(DA/(DA-DB));++Cuts;}
    }
    Center=Cuts?Center/Cuts:N*H;
    constexpr int32 Rings=UE_ARRAY_COUNT(LiquidProfile);
    FVector2D RingNormals[Rings];
    for(int32 R=0;R<Rings;++R)
    {
        const FVector2D Before=R>0?LiquidProfile[R]-LiquidProfile[R-1]:LiquidProfile[1]-LiquidProfile[0];
        const FVector2D After=R+1<Rings?LiquidProfile[R+1]-LiquidProfile[R]:Before;
        RingNormals[R]=(FVector2D(Before.X,-Before.Y).GetSafeNormal()+FVector2D(After.X,-After.Y).GetSafeNormal()).GetSafeNormal();
    }
    auto Emit=[&](int32 Slot,const FVector& A,const FVector& B,const FVector& C,const FVector& Normal,bool bSmoothWall=false)
    {
        Vertices[Slot]=A;Vertices[Slot+1]=B;Vertices[Slot+2]=C;
        for(int32 J=0;J<3;++J)
        {
            const FVector& V=Vertices[Slot+J];Normals[Slot+J]=Normal;UV[Slot+J]=FVector2D(V.X,V.Y)*.1;
            if(bSmoothWall && FMath::Abs(Normal.Z)<.999)
            {
                int32 R=0;while(R+2<Rings && V.Z>LiquidProfile[R+1].X)++R;
                const double Alpha=FMath::Clamp((V.Z-LiquidProfile[R].X)/(LiquidProfile[R+1].X-LiquidProfile[R].X),0.,1.);
                const FVector2D Radial=FVector2D(V.X,V.Y).GetSafeNormal();
                const FVector2D Slope=FMath::Lerp(RingNormals[R],RingNormals[R+1],Alpha).GetSafeNormal();
                Normals[Slot+J]=FVector(Radial.X*Slope.X,Radial.Y*Slope.X,Slope.Y);
            }
        }
    };
    for(int32 I=0;I<Faces.Num();I+=3)
    {
        const FVector P[3]={Cavity[Faces[I]],Cavity[Faces[I+1]],Cavity[Faces[I+2]]};FVector Q[4];
        const int32 Count=Clip(P,N,H,Q),Slot=I*3;
        const FVector WallNormal=FVector::CrossProduct(P[1]-P[0],P[2]-P[0]).GetSafeNormal();
        Emit(Slot,Count>=3?Q[0]:Center,Count>=3?Q[1]:Center,Count>=3?Q[2]:Center,WallNormal,true);
        Emit(Slot+3,Count==4?Q[0]:Center,Count==4?Q[2]:Center,Count==4?Q[3]:Center,WallNormal,true);
        FVector A=Center,B=Center;
        for(int32 J=0;J<Count;++J)if(FMath::Abs(FVector::DotProduct(N,Q[J])-H)<1.e-6 && FMath::Abs(FVector::DotProduct(N,Q[(J+1)%Count])-H)<1.e-6)
        {A=Q[(J+1)%Count];B=Q[J];break;}
        Emit(Slot+6,Center,A,B,N);
    }
    if(GetNumSections()==0)CreateMeshSection_LinearColor(0,Vertices,Triangles,Normals,UV,Colors,Tangents,false);
    else UpdateMeshSection_LinearColor(0,Vertices,Normals,UV,Colors,Tangents);
    DrawnNormal=N;DrawnFill=FillAmount;++MeshUpdates;
    LastUpdateMicroseconds=(FPlatformTime::Seconds()-Start)*1.e6;
}
