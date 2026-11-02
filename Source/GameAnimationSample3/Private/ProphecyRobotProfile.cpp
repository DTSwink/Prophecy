#include "ProphecyRobotProfile.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
namespace ProphecyRobot
{
namespace
{
using FObject=TSharedPtr<FJsonObject>;
FVector V(const TArray<TSharedPtr<FJsonValue>>& A){return FVector(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber());}
FTransform T(const FObject& O)
{
    const auto& Q=O->GetArrayField(TEXT("q"));
    return FTransform(FQuat(Q[0]->AsNumber(),Q[1]->AsNumber(),Q[2]->AsNumber(),Q[3]->AsNumber()).GetNormalized(),V(O->GetArrayField(TEXT("p")))*100.);
}
}
const FProfile* Profile(FString& Error)
{
    static TUniquePtr<FProfile> Cached;
    if(Cached)return Cached.Get();
    FString Text;FObject Json;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("locomotion/NN/robots/rig.json"))) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Json) || !Json ||
        Json->GetIntegerField(TEXT("schema"))!=1 || Json->GetArrayField(TEXT("bodies")).Num()!=15 || Json->GetArrayField(TEXT("joints")).Num()!=14)
    {Error=TEXT("The packaged robot rig is missing or has an unsupported schema.");return nullptr;}
    auto P=MakeUnique<FProfile>();
    for(const auto& Value:Json->GetArrayField(TEXT("bodies")))
    {
        const auto O=Value->AsObject();auto& B=P->Bodies.AddDefaulted_GetRef();
        B.Bone=FName(O->GetStringField(TEXT("bone")));B.BodyFromBone=T(O->GetObjectField(TEXT("body_from_bone")));
        B.MassFrame=T(O->GetObjectField(TEXT("mass_frame")));B.Mass=O->GetNumberField(TEXT("mass"));
        B.Inertia=V(O->GetArrayField(TEXT("inertia")))*10000.;
        for(const auto& A:O->GetArrayField(TEXT("aliases")))B.Aliases.Add(FName(A->AsString()));
        const auto& D=O->GetArrayField(TEXT("drag"));B.Drag.Coefficient=D[0]->AsNumber();B.Drag.First=V(D[1]->AsArray());
        for(int32 I=0;I<3;++I)B.Drag.Second[I]=V(D[2]->AsArray()[I]->AsArray());
        for(const auto& S:O->GetArrayField(TEXT("shapes")))
        {
            const auto G=S->AsObject();const FString Kind=G->GetStringField(TEXT("kind"));const auto& Size=G->GetArrayField(TEXT("size"));
            auto& Shape=B.Shapes.AddDefaulted_GetRef();Shape.SourceElementIndex=B.Shapes.Num()-1;
            Shape.LocalToBodyOrigin=T(G->GetObjectField(TEXT("frame")));
            if(Kind==TEXT("box")){Shape.Kind=EProphecyJoltRigShape::Box;Shape.BoxHalfExtentCm=V(Size)*100.;}
            else {Shape.RadiusCm=Size[0]->AsNumber()*100.;Shape.Kind=Kind==TEXT("capsule")?EProphecyJoltRigShape::Capsule:EProphecyJoltRigShape::Sphere;
                if(Shape.Kind==EProphecyJoltRigShape::Capsule)Shape.CapsuleCylinderLengthCm=Size[1]->AsNumber()*200.;}
            Shape.AuthoredLocalToBodyOrigin=Shape.LocalToBodyOrigin;Shape.AuthoredRadiusCm=Shape.RadiusCm;
            Shape.AuthoredBoxHalfExtentCm=Shape.BoxHalfExtentCm;Shape.AuthoredCapsuleCylinderLengthCm=Shape.CapsuleCylinderLengthCm;
            Shape.AuthoredCollisionEnabled=Shape.CurrentCollisionEnabled=ECollisionEnabled::QueryAndPhysics;
            Shape.bNativeSimulationEnabled=Shape.bNativeQueryEnabled=Shape.bContributesToAuthoredMass=true;
        }
    }
    for(const auto& Value:Json->GetArrayField(TEXT("joints")))
    {
        const auto O=Value->AsObject();auto& J=P->Joints.AddDefaulted_GetRef();
        J.Name=FName(O->GetStringField(TEXT("name")));J.Parent=O->GetIntegerField(TEXT("parent"));J.Child=O->GetIntegerField(TEXT("child"));
        J.Action=O->GetIntegerField(TEXT("action"));J.ParentFrame=T(O->GetObjectField(TEXT("parent_frame")));J.Bounds=V(O->GetArrayField(TEXT("bounds")));
        const auto& Q=O->GetArrayField(TEXT("rest"));J.Rest=FQuat(Q[1]->AsNumber(),Q[2]->AsNumber(),Q[3]->AsNumber(),Q[0]->AsNumber()).GetNormalized();
        for(int32 I=0;I<2;++I){J.Motor[I].Damping=O->GetNumberField(TEXT("gain"));J.Motor[I].bBall=O->GetBoolField(TEXT("ball"));J.Motor[I].TorqueLimit=V(O->GetArrayField(TEXT("caps"))[I]->AsArray());}
    }
    for(const auto& Value:Json->GetArrayField(TEXT("disabled_pairs")))
    {
        const auto& A=Value->AsArray();int32 X=A[0]->AsNumber(),Y=A[1]->AsNumber();
        P->Disabled.Add({FMath::Min(X,Y),FMath::Max(X,Y),true,false});
    }
    Cached=MoveTemp(P);return Cached.Get();
}
bool MakeSnapshot(const FProfile& P,USkeletalMeshComponent& Mesh,TConstArrayView<FBodyState> Entry,FProphecyJoltRigSnapshot& S,FString& Error)
{
    if(Entry.Num()!=P.Bodies.Num() || !Mesh.GetComponentScale().Equals(FVector::OneVector,.001))
    {Error=TEXT("Robot admission requires the trained unit-scale mannequin and 15 captured bodies.");return false;}
    const auto Source=S.Bodies;
    S.Bodies.Reset();S.Joints.Reset();S.DisabledPairs=P.Disabled;
    for(int32 I=0;I<P.Bodies.Num();++I)
    {
        const auto& Spec=P.Bodies[I];const auto* Old=Source.FindByPredicate([&](const auto& B){return B.BodyName==Spec.Bone;});
        if(!Old){Error=FString::Printf(TEXT("Robot source is missing %s."),*Spec.Bone.ToString());return false;}
        auto& B=S.Bodies.Add_GetRef(*Old);B.SourceBodyIndex=I;B.BodyOriginToWorld=Entry[I].World;
        B.MassKg=Spec.Mass;B.MassFrameToBodyOrigin=Spec.MassFrame;B.PrincipalInertiaKgCmSquared=Spec.Inertia;
        B.CenterOfMassVelocityCmPerSecond=Entry[I].COMVelocity;B.AngularVelocityRadiansPerSecond=Entry[I].AngularVelocity;
        B.Shapes=Spec.Shapes;B.bSimulating=B.bAwake=B.bGravityEnabled=true;B.bCCD=false;B.bMACD=false;B.bInertiaConditioning=false;
        B.LinearDamping=B.AngularDamping=0;B.VelocitySolverIterations=40;B.PositionSolverIterations=8;
        B.MaxAngularVelocityRadiansPerSecond=62.831851959228516;
        B.MaxLinearVelocityCmPerSecond=1.8446742974197924e19;
        B.Friction=B.StaticFriction=1;B.Restitution=0;
        for(auto& Shape:B.Shapes){Shape.NativeSimulationObjectType=B.ObjectType;Shape.NativeSimulationResponses=B.CollisionResponses;}
    }
    for(int32 I=0;I<P.Joints.Num();++I)
    {
        const auto& Spec=P.Joints[I];auto& J=S.Joints.AddDefaulted_GetRef();
        J.SourceConstraintIndex=I;J.JointName=Spec.Name;J.Body1Index=Spec.Child;J.Body2Index=Spec.Parent;
        J.Bone1=P.Bodies[Spec.Child].Bone;J.Bone2=P.Bodies[Spec.Parent].Bone;J.Frame2=Spec.ParentFrame;
        auto& C=J.CurrentProfile;C.LinearLimit.XMotion=C.LinearLimit.YMotion=C.LinearLimit.ZMotion=LCM_Locked;
        C.TwistLimit.TwistMotion=Spec.Bounds.X>0?ACM_Limited:ACM_Locked;
        C.ConeLimit.Swing2Motion=Spec.Bounds.Y>0?ACM_Limited:ACM_Locked;
        C.ConeLimit.Swing1Motion=Spec.Bounds.Z>0?ACM_Limited:ACM_Locked;
        C.TwistLimit.TwistLimitDegrees=FMath::RadiansToDegrees(Spec.Bounds.X);
        C.ConeLimit.Swing2LimitDegrees=FMath::RadiansToDegrees(Spec.Bounds.Y);
        C.ConeLimit.Swing1LimitDegrees=FMath::RadiansToDegrees(Spec.Bounds.Z);
        C.bDisableCollision=true;C.bEnableProjection=false;
    }
    return ProphecyJolt::Rig::ValidateSnapshot(S,Error);
}
void Observation(const FProfile& P,TConstArrayView<FBodyState> B,bool Clanker,float Gait,const FVector& Direction,bool SwordDrawn,const FVector2f& Phase,TArrayView<float> Out)
{
    check(B.Num()==15&&Out.Num()==154);int32 N=0;
    const FQuat Basis(FVector::UpVector,PI*.5);
    auto Vec=[&](FVector V){Out[N++]=V.X;Out[N++]=V.Y;Out[N++]=V.Z;};
    auto Rot=[&](FQuat Q){Vec(Q.RotateVector(FVector::ForwardVector));Vec(Q.RotateVector(FVector::UpVector));};
    Out[N++]=B[0].World.GetLocation().Z*.01;Rot(Basis*B[0].World.GetRotation());
    // Both frozen Newton policies read root joint_qd, whose linear part is COM velocity.
    Vec(Basis.RotateVector(B[0].COMVelocity)*.01);Vec(Basis.RotateVector(B[0].AngularVelocity));
    for(const auto& J:P.Joints)Rot((J.Rest.Inverse()*B[J.Parent].World.GetRotation().Inverse()*B[J.Child].World.GetRotation()).GetNormalized());
    for(const auto& J:P.Joints)
    {
        const FVector W=B[J.Child].World.GetRotation().UnrotateVector(B[J.Child].AngularVelocity-B[J.Parent].AngularVelocity);
        if(J.Motor[0].bBall)Vec(W);else Out[N++]=W.Z;
    }
    for(int32 I:{2,5,8,11,14})Vec(Basis.RotateVector(B[I].World.GetLocation()-B[0].World.GetLocation())*.01);
    Out[N++]=Clanker?Gait:-1;FVector D=Basis.RotateVector(Direction).GetSafeNormal2D();
    if(!Clanker||Gait<0||D.IsNearlyZero())D=FVector::ForwardVector;
    Out[N++]=D.X;Out[N++]=D.Y;Out[N++]=SwordDrawn?1:0;Out[N++]=1;Out[N++]=1;Out[N++]=Phase.X;Out[N++]=Phase.Y;
    check(N==154);
}
}
