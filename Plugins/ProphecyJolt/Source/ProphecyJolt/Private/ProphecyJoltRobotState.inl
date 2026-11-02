// Inside WorldPrivate. All state is owned by an admitted rig, never by an asset.
struct FRobotRig final : JPH::PhysicsStepListener
{
    JPH::PhysicsSystem* Physics=nullptr;
    TArray<JPH::BodyID> Bodies;
    TArray<FProphecyJoltRobotDrag> Drag;
    TArray<JPH::Ref<ProphecyJolt::FSphericalLimit>> Limits;
    TArray<FQuat> ChildFrames;
    TArray<FVector> Bounds;
    TArray<JPH::Vec3> PreviousForce,PreviousTorque;
    void OnStep(const JPH::PhysicsStepListenerContext& Context)override
    {
        auto& BI=Physics->GetBodyInterfaceNoLock();
        for(int32 I=0;I<Bodies.Num();++I)
        {
            const auto& D=Drag[I];const auto Rotation=BI.GetRotation(Bodies[I]);
            JPH::Vec3 V,W;BI.GetLinearAndAngularVelocity(Bodies[I],V,W);
            auto Vector=[](const FVector& X){return JPH::Vec3(float(X.X),float(X.Y),float(X.Z));};
            const JPH::Vec3 First=Rotation*Vector(D.First),LocalW=Rotation.Conjugated()*W;
            const JPH::Vec3 Tensor(Vector(D.Second[0]).Dot(LocalW),Vector(D.Second[1]).Dot(LocalW),Vector(D.Second[2]).Dot(LocalW));
            // Jolt retains force accumulators across collision substeps. Replace
            // this listener's contribution instead of adding it four/eight times.
            if(Context.mIsFirstStep){PreviousForce[I]=PreviousTorque[I]=JPH::Vec3::sZero();}
            const auto Force=-D.Coefficient*V-W.Cross(First),Torque=-First.Cross(V)-Rotation*Tensor;
            BI.AddForceAndTorque(Bodies[I],Force-PreviousForce[I],Torque-PreviousTorque[I]);
            PreviousForce[I]=Force;PreviousTorque[I]=Torque;
        }
    }
};
static TMap<const FRigRecord*,TUniquePtr<FRobotRig>> Robots;
static TMap<const JPH::PhysicsSystem*,TMap<uint32,const FRigRecord*>> RobotBodies;
static void RemoveRobotRig(JPH::PhysicsSystem& Physics,const FRigRecord* Rig)
{
    if(auto* S=Robots.Find(Rig))
    {
        Physics.RemoveStepListener(S->Get());
        for(const auto& C:(*S)->Limits)if(C)Physics.RemoveConstraint(C.GetPtr());
        if(auto* Tags=RobotBodies.Find(&Physics))
        {
            for(const auto& B:(*S)->Bodies)Tags->Remove(B.GetIndexAndSequenceNumber());
            if(Tags->IsEmpty())RobotBodies.Remove(&Physics);
        }
        Robots.Remove(Rig);
    }
}
static void RobotContact(const JPH::PhysicsSystem& Physics,const JPH::Body& A,const JPH::Body& B,
    const JPH::ContactManifold& M,JPH::ContactSettings& Contact)
{
    if(RobotBodies.IsEmpty())return;
    const auto* Tags=RobotBodies.Find(&Physics);if(!Tags)return;
    const auto* RA=Tags->Find(A.GetID().GetIndexAndSequenceNumber());
    const auto* RB=Tags->Find(B.GetID().GetIndexAndSequenceNumber());
    if(!RA&&!RB)return;
    // Both trained robots use actual touching points, including in mixed
    // manifolds. Other body pairs keep Jolt's default speculative response.
    Contact.mEnableSpeculativeContacts=false;
    if(RA&&RB&&*RA==*RB)Contact.mCombinedFriction=0;
    else if(A.IsStatic()||B.IsStatic()){Contact.mCombinedFriction=1;Contact.mCombinedRestitution=0;}
}
