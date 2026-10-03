from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyNNPoseTypes.cpp');s=p.read_text();a=s.index('bool ProphecyNNPresentation::ReadBoneWorld(')
s=s[:a]+r'''bool ProphecyNNPresentation::ReadBoneWorld(int32 Id,FName Bone,FTransform& Out,FTransform* PreviousEndpoint,FTransform* CurrentEndpoint)
{
    const bool Foot=Bone==TEXT("foot_l") || Bone==TEXT("foot_r");
    TArray<FName,TInlineAllocator<3>> Names;
    TArray<FTransform,TInlineAllocator<3>> Sampled,Previous,Current;
    FProphecyNNPoseSnapshot Leg;
    {
        FReadScopeLock Lock(GProphecyNNPoseLock);
        const auto* Found=GProphecyNNPoses.Find(Id);if(!Found)return false;
        const auto& P=*Found;
        const auto* Presentation=GProphecyNNPresentation.Find(Id);
        const float Alpha=Presentation && Presentation->SourceTimeSeconds==P.SourceTimeSeconds?Presentation->Alpha:1.f;
        if(Foot)
        {
            const bool Right=Bone==TEXT("foot_r");
            Names={Right?FName(TEXT("thigh_r")):FName(TEXT("thigh_l")),Right?FName(TEXT("calf_r")):FName(TEXT("calf_l")),Bone};
            Leg.CalfClampLeewayCm=P.CalfClampLeewayCm;Leg.CalfClampLengths=P.CalfClampLengths;
        }
        else Names.Add(Bone);
        for(FName Name:Names)
        {
            const int32 I=P.BoneNames.IndexOfByKey(Name);
            if(!P.ComponentTransforms.IsValidIndex(I)||!P.PreviousComponentTransforms.IsValidIndex(I))return false;
            const FTransform A=P.PreviousComponentTransforms[I]*P.PreviousComponentWorldTransform;
            const FTransform B=P.ComponentTransforms[I]*P.ComponentWorldTransform;
            FTransform Value;
            if(P.InterpolationMode==EProphecyNNInterpolationMode::HermiteSlerp) Value=ProphecyNNInterpolation::Sample(P,I,A,B,Alpha);
            else
            {
                FQuat Start=A.GetRotation().GetNormalized(),End=B.GetRotation().GetNormalized();
                float Cos=Start|End;if(Cos<0){End=End*-1.;Cos=-Cos;}
                const float Angle=2.f*FMath::Acos(FMath::Clamp(Cos,0.f,1.f));
                const FQuat Q=Angle<=1.e-6f?Start:FQuat::Slerp(Start,End,
                    FMath::Atan2(Alpha*FMath::Sin(Angle),(1.f-Alpha)+Alpha*FMath::Cos(Angle))/Angle).GetNormalized();
                Value=FTransform(Q,FMath::Lerp(A.GetLocation(),B.GetLocation(),Alpha));
            }
            Sampled.Add(Value);Previous.Add(A);Current.Add(B);
            if(Foot)
            {
                if(!P.LocalTransforms.IsValidIndex(I))return false;
                Leg.BoneNames.Add(Name);Leg.LocalTransforms.Add(P.LocalTransforms[I]);
            }
        }
    }
    if(Foot)
    {
        // Capture the same corrected ankle seen by rendering/physical targets,
        // including calf recovery, authored clamp and optional knee soft reach.
        // Release the store lock before the shared correction reads its settings.
        FProphecyNNPoseStore::ApplyRigidCalves(Id,Leg,Names,Sampled);
        if(PreviousEndpoint)FProphecyNNPoseStore::ApplyRigidCalves(Id,Leg,Names,Previous);
        if(CurrentEndpoint)FProphecyNNPoseStore::ApplyRigidCalves(Id,Leg,Names,Current);
    }
    Out=Sampled.Last();
    if(PreviousEndpoint)*PreviousEndpoint=Previous.Last();
    if(CurrentEndpoint)*CurrentEndpoint=Current.Last();
    return true;
}
''';p.write_text(s)
