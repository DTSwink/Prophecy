exec((__import__('pathlib').Path(__file__).with_name('EditFixedArms.py')).read_text().split("edit('Source/GameAnimationSample3/Public/ProphecyAgent.h'")[0])
def profiles(s):
 s=s.replace('L==ELimb::Foot?S.Foot:L==ELimb::Calf?S.Calf:L==ELimb::Hand?S.Hand:S.Forearm','L==ELimb::Foot?S.Foot:S.Calf')
 s=s.replace('return {true,A.bAttackHandClamp,A.AttackHandClampLeewayCm};','return {};')
 s=sub(s,r'    if \(L==ELimb::Hand\) return[^\n]*\n    return \{true,A.bLocomotionForearmClamp[^\n]*','    return {};')
 s=s.replace('return {true,L==ELimb::Hand,0};','return {true,false,0};')
 s=s.replace('L==ELimb::Foot?It->bClampFoot:L==ELimb::Calf?It->bClampCalf:It->bClampHand','L==ELimb::Foot?It->bClampFoot:It->bClampCalf')
 s=sub(s,r'        else \{ A.bAttackHandClamp[^\n]*\n','')
 s=sub(s,r'    else if \(L==ELimb::Hand\)[^\n]*\n    else \{ A.bLocomotionForearmClamp[^\n]*\n','')
 s=s.replace('{ELimb::Foot,ELimb::Calf,ELimb::Hand,ELimb::Forearm}','{ELimb::Foot,ELimb::Calf}').replace('if (!(M==EMode::Attack && L==ELimb::Forearm)) Saved.Add','Saved.Add')
 s=s.replace('    if (!Hand && !Foot) return {};','    if (Hand) return TEXT(" / Arm=FixedLength");\n    if (!Foot) return {};')
 s=sub(s,r'    return FString::Printf\(TEXT\(" / Clamp=%s:%s %s:%s"\).*?\);','    return FString::Printf(TEXT(" / Clamp=Foot:%s Calf:%s"),*Text(ELimb::Foot),*Text(ELimb::Calf));')
 s=sub(s,r'    case EProphecyClampType::(?:Forearm|Hand):[^\n]*\n','',2)
 s=sub(s,r'    A->SetLocomotionHandClamp\(true,5\);A->SetLocomotionForearmClamp\(false,7\);\n    A->SetAttackHandClamp\(false,11\);\n','')
 s=s.replace('ELimb::Hand,true,13','ELimb::Calf,true,13').replace(';A->SetLocomotionHandClamp(true,55)','')
 s=sub(s,r'    TestEqual\(TEXT\("Foot restore does not affect hands"\)[^\n]*\n','')
 s=sub(s,r'    TestTrue\(TEXT\("Forearm restores independently"\).*?(?=    TestTrue\(TEXT\("Parry inherited)', '''    ProphecyDefenseControls::Set(A,true,ELimb::Calf,false,0);
    TestEqual(TEXT("All restores eight leg settings"),Lib::BlendAllClampsToSnapshot(A,0,TEXT("ClampBase")),8);
    TestTrue(TEXT("Dodge restored independently"),ProphecyDefenseControls::Find(A,true)->Calf.bEnabled && ProphecyDefenseControls::Find(A,true)->Calf.LeewayCm==13);
''')
 s=s.replace('Hands print locomotion only','Hands report their invariant').replace(' / Clamp=Hand:5.00 Forearm:off',' / Arm=FixedLength')
 return s
edit('Source/GameAnimationSample3/Private/ProphecyClampProfiles.inl',profiles)
edit('Source/GameAnimationSample3/Private/ProphecyPhysicalProfileDebug.cpp',lambda s:s.replace('Locomotion Clamp Leeway (cm)','Leg Clamp Leeway (cm) / Arm Attachment'))
edit('Source/GameAnimationSample3/Public/ProphecyPhysicalProfileLibrary.h',lambda s:s.replace('Hand/foot rows also show locomotion Hand/Forearm or Foot/Calf clamp leeway (off when disabled).','Hands show fixed attachment; feet show locomotion Foot/Calf clamp leeway (off when disabled).'))

def slash(s):
 s=s.replace('true, false, 0, FVector2D::ZeroVector, Agent.Slash.HandClamp','true, false, 0, FVector2D::ZeroVector, Snapshot.FixedArms')
 # The rebase path has the snapshot named Pose, verified separately if needed.
 s=sub(s,r'\t\t// Default matches the reference animation.*?\t\tconst USkeletalMeshComponent\* Mesh', '\t\t// Hands remain at their anatomical forearm attachment in every attack.\n\t\tconst USkeletalMeshComponent* Mesh')
 s=sub(s,r'\t\t\t\t\tSlash.HandClamp.ReferenceOffsets[^\n]*\n\t\t\t\t\tif \(Slash.HandClamp.bEnabled\)\n\t\t\t\t\t\tPose\[Arm.End\].SetTranslation\(FProphecyNNAttackHandClamp::ClampPosition\(\n[^\n]*\n','\t\t\t\t\tPose[Arm.End].SetTranslation(Pose[Arm.Mid].TransformPosition(Offset));\n')
 return s
edit('Source/GameAnimationSample3/Private/ProphecyNNSlashRuntime.inl',slash)

edit('Source/GameAnimationSample3/Private/ProphecyUpperBodyInertia.h',lambda s:sub(s,r'const FVector2D& RestForearmLengthsCm,bool ClampForearm,double ForearmLeewayCm,\n    bool ClampHand,double HandLengthMultiplier,double HandLeewayCm,','const FVector2D& RestForearmLengthsCm,'))
def inertia(s):
 s=s.replace('    double InitialLength=0;\n','').replace('static TMap<TWeakObjectPtr<const AProphecyAgent>,FVector2D> ArmLengthVelocities;\n','')
 s=s.replace('Clean(ArmLengthVelocities);','').replace('ArmLengthVelocities.Remove(A);','').replace('ArmLengthVelocities.Add(A,FVector2D::ZeroVector);','')
 s=s.replace('        M.InitialLength=M.LocalLower.Length();\n','')
 s=sub(s,r'double Dt,const FVector2D& RestLengths,bool ClampForearm,double ForearmLeeway,\n    bool ClampHand,double HandMultiplier,double HandLeeway,','double Dt,const FVector2D& RestLengths,')
 s=sub(s,r'    if\(ClampForearm\)ForearmLeeway=[^\n]*\n    if\(ClampHand\)HandLeeway=[^\n]*\n','')
 s=sub(s,r'    auto\* LengthVelocities=ArmLengthVelocities.Find\(A\);if\(!LengthVelocities\)return;\n','')
 s=sub(s,r'        const double GoalLength=ClampForearm.*?        FTransform LocalGoal\[3\];', '''        const double GoalLength=Rest;
        Goal[2].SetLocation(Goal[1].GetLocation()+RawLower.GetSafeNormal(1.e-12,
            Goal[1].GetRotation().RotateVector(M.LocalLower.GetSafeNormal()))*Rest);
        FTransform LocalGoal[3];''')
 s=sub(s,r'        // Wrist motion and chain length must share a response.*?        const double Length=FMath::Lerp\([^\n]*\n','        const double Length=Rest;\n')
 s=s.replace('Target,M.LocalUpper,M.LocalPole,1.);','Target,M.LocalUpper,M.LocalPole,1.,Rest);')
 s=s.replace(' length=%.4f leeway=%.4f',' length=%.4f').replace('RawLength,GoalLength,Length,ForearmLeeway,','RawLength,GoalLength,Length,')
 # Update all focused test calls to the simplified fixed-geometry API.
 s=re.sub(r'FVector2D\((\d+),(\d+)\),(?:true|false),\d+,(?:true|false),1,0',r'FVector2D(\1,\2)',s)
 s=s.replace('FVector2D(25,25)','FVector2D(30,30)')
 s=s.replace('Outgoing forearm length is not snapped to locomotion clamp at entry','Inertia keeps the anatomical forearm length')
 s=sub(s,r'    // A wrist retracting along its forearm.*?(?=    Cancel\(A\);TestFalse\(TEXT\("Cancel removes arm sidecar)', '''    // Arbitrary decoded lengths and every influence must retain the one rest length.
    for(const float Weight:{.25f,.5f,1.f})
    {
        UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,.025,0,.5,1,ESpace::RootLocal,Weight);
        Begin(A,Last,Last,Names,Core,1./30);
        for(int32 Step=0;Step<15;++Step)
        {
            Returns.FindChecked(A).Elapsed=double(Step+1)/30.;Pose=Last;
            for(int32 I:{4,8})Pose[I].SetLocation(Last[I-1].GetLocation()+FVector(0,0,Step%2?-16.:-60.));
            ApplyArms(A,FTransform::Identity,Pose,1./30,FVector2D(30,30));
            for(int32 I:{4,8})
            {
                TestTrue(TEXT("Fixed wrist goal does not kick a stationary elbow sideways"),Pose[I-1].GetLocation().Equals(Last[I-1].GetLocation(),1.e-5));
                TestTrue(TEXT("Forearm never stretches or compresses during inertia/blend"),FMath::IsNearlyEqual((Pose[I].GetLocation()-Pose[I-1].GetLocation()).Length(),30.,1.e-5));
            }
        }
    }
''')
 s=sub(s,r'    TestFalse\(TEXT\("Cancel removes length spring"\)[^\n]*\n','')
 return s
edit('Source/GameAnimationSample3/Private/ProphecyUpperBodyInertiaLibrary.cpp',inertia)
edit('Source/GameAnimationSample3/Private/ProphecyHandInertiaRuntime.inl',lambda s:sub(s,r'            FVector2D\(Impl->UpperArms\[0\].Lengths.Y\*100.,Impl->UpperArms\[1\].Lengths.Y\*100.\),\n            Actor->bLocomotionForearmClamp.*?Root\);','            FVector2D(Impl->UpperArms[0].Lengths.Y*100.,Impl->UpperArms[1].Lengths.Y*100.),Root);').replace('LocalTrainingToUnreal(A.LocalPoleAxes[0]),HandChainFollow(Temper,Recovery,I));','LocalTrainingToUnreal(A.LocalPoleAxes[0]),HandChainFollow(Temper,Recovery,I),A.Lengths.Y*100.);'))
edit('Source/GameAnimationSample3/Public/ProphecyUpperBodyInertiaLibrary.h',lambda s:s.replace('outgoing forearm lengths blend to the locomotion clamp range. Response','forearms retain their fixed anatomical length. Response'))
edit('Source/GameAnimationSample3/Private/ProphecyHandChainMath.h',lambda s:s.replace('const FVector& LocalUpper,const FVector& LocalPole,double Follow)','const FVector& LocalUpper,const FVector& LocalPole,double Follow,double ForearmLength)').replace('''    // Honor the source's allowed forearm length; forcing rest length here made
    // unclamped NN arms change length abruptly when reconstruction switched off.
    const double L2=FMath::Lerp((PreviousWrist.GetLocation()-PreviousElbow.GetLocation()).Length(),
        (Wrist.GetLocation()-Elbow.GetLocation()).Length(),Follow);''','    const double L2=ForearmLength; // Geometry never blends with pose ownership.'))
def entry(s):
 s=s.replace('FVector Position,Velocity,AngularVelocity,LocalUpper,LocalPole;','FVector Position,Velocity,AngularVelocity,LocalUpper,LocalPole;\n    double ForearmLength=0;')
 s=s.replace('        M.Position=M.Accepted[2].GetLocation();','        M.ForearmLength=FVector::Distance(M.Accepted[1].GetLocation(),M.Accepted[2].GetLocation());\n        M.Position=M.Accepted[2].GetLocation();')
 s=sub(s,r'        const double UpperLength=FMath::Lerp\([^\n]*\n        const FVector LocalUpper=M.LocalUpper.GetSafeNormal\(\)\*UpperLength;','        const FVector LocalUpper=M.LocalUpper;')
 s=s.replace('Target,LocalUpper,M.LocalPole,Follow);','Target,LocalUpper,M.LocalPole,Follow,M.ForearmLength);')
 return s
edit('Source/GameAnimationSample3/Private/ProphecyAttackStartHandInertia.cpp',entry)
def neutral(s):
 s=sub(s,r'    const double NeutralLower=.*?    const double CosBend=', '    const double LowerLength=FVector::Distance(Elbow.GetLocation(),Wrist.GetLocation());\n    const double CosBend=')
 s=s.replace('Target,LocalUpper,LocalPole,Alpha);','Target,LocalUpper,LocalPole,Alpha,LowerLength);').replace('FMath::Lerp(RotationStep,1.,Alpha));','FMath::Lerp(RotationStep,1.,Alpha),LowerLength);')
 return s
edit('Source/GameAnimationSample3/Private/ProphecySlashReturnLibrary.cpp',neutral)
print('Removed arm snapshot/easing/length springs; all chain solvers take one fixed forearm length')
