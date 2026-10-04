// On-demand readback. Never use gameplay accessors that consume clocks here.
bool AProphecyNNLocomotionManager::DescribeNNModifiers(const AProphecyAgent* A,ProphecyNNModifierDebug::FReport& R) const
{
    if(!Impl || !A || ResolveAgent(A->GetAgentHandle())!=A || !Impl->Agents.IsValidIndex(A->GetAgentHandle().Index))return false;
    const auto& S=Impl->Agents[A->GetAgentHandle().Index];const auto& Slash=S.Slash;
    R.Attack=Slash.bActive;R.Half=R.Attack&&Slash.bHalf;
    R.Defense=S.DefensePose&&S.DefensePose->bHasPose;R.Dodge=R.Defense&&S.DefensePose->bDodge;
    R.LowerLoco=!S.DefensePose&&(!R.Attack||R.Half);
    R.UpperLoco=!R.Attack&&!R.Defense&&!ProphecyArmedPose::Active(A);R.Walk=S.PublishedWalkWeight;
    R.WalkFeet=S.RecoveryWeights.Left>0 || S.RecoveryWeights.Right>0;
    R.Regional=S.RecoveryWeights.Left!=S.RecoveryWeights.Pelvis || S.RecoveryWeights.Right!=S.RecoveryWeights.Pelvis;
    R.RecoveryPresentation=UsePresentationRecovery();
    float Interval=0;bool Interpolate=false;A->GetNNPoseDataSource(R.PoseId,Interval,Interpolate);
    R.Add(TEXT("Mode"),TEXT("STATE"),TEXT("NN ownership"),FString::Printf(TEXT("%s%s | inference %s | lower Walk %.3f L %.3f R %.3f | %.3g Hz"),
        R.Attack?*Slash.Family.ToString():R.Defense?(R.Dodge?TEXT("dodge"):TEXT("parry")):TEXT("locomotion"),
        R.Half?TEXT(" HALF"):TEXT(""),A->bNNInferenceEnabled?TEXT("enabled"):TEXT("PAUSED"),
        R.Walk,S.PublishedLegWalkWeights.X,S.PublishedLegWalkWeights.Y,NNUpdateHz));
    if(!A->bNNInferenceEnabled)
        R.Add(TEXT("FrozenNN"),TEXT("INPUT"),TEXT("NN disabled"),TEXT("pose/history frozen; other rows describe retained state and presentation"));
    if(S.PolicyBlend.IsActive() && R.LowerLoco)
        R.Add(TEXT("PolicyBlend"),TEXT("POSE+HISTORY"),TEXT("Walk / Run blend"),FString::Printf(TEXT("Walk %.3f -> %d | %.3f / %.3f"),S.PolicyBlend.WalkWeight,S.PolicyBlend.bTargetWalk,S.PolicyBlend.Elapsed,S.PolicyBlend.Duration));
    if(R.LowerLoco && (S.RecoveryWeights.Pelvis!=S.PolicyBlend.WalkWeight || S.RecoveryWeights.Left!=S.PolicyBlend.WalkWeight || S.RecoveryWeights.Right!=S.PolicyBlend.WalkWeight))
        R.Add(TEXT("RegionalRecovery"),TEXT("POSE+HISTORY"),TEXT("Regional locomotion recovery"),FString::Printf(TEXT("Walk pelvis %.3f left %.3f right %.3f | normal %.3f"),S.RecoveryWeights.Pelvis,S.RecoveryWeights.Left,S.RecoveryWeights.Right,S.PolicyBlend.WalkWeight));
    if(R.LowerLoco)
    {
        const auto W=ProphecyAttackRecovery::FootRotationWeights(A,S.PolicyBlend.WalkWeight);
        if(W.X>=0 || W.Y>=0)R.Add(TEXT("RotationRecovery"),TEXT("POSE+HISTORY"),TEXT("Walk foot-rotation recovery"),FString::Printf(TEXT("Walk L %.3f R %.3f (-1 inherits)"),W.X,W.Y));
    }
    const float Dilation=GetAgentTimeDilation(A->GetAgentHandle());
    if(Dilation!=1)R.Add(TEXT("AgentClock"),TEXT("CLOCK"),TEXT("Agent NN / physics time scale"),FString::Printf(TEXT("%.3g | blend durations remain 60 game ticks"),Dilation));
    if(!R.Attack && !R.Defense && !ProphecyArmedPose::OwnsUpperOutput(A))
    {
        R.Add(TEXT("UpperInputs"),TEXT("INPUT"),TEXT("Upper gaze / equipment"),FString::Printf(TEXT("yaw %.3f pitch %.3f sword %d"),A->UpperNNGazeYawNormalized,A->UpperNNGazePitchNormalized,A->bUpperNNHasSword));
        if(S.UpperRootRotationHorizon!=1)R.Add(TEXT("RootHorizon"),TEXT("INPUT"),TEXT("Upper root rotation horizon"),FString::Printf(TEXT("%.3g"),S.UpperRootRotationHorizon));
    }
    if(const auto* B=ProphecyRootBalance::GetPrepared(A);B && prophecy::sim::IsRootBalanceActive(S.MoverState,S.MoverIntent,*B))
        R.Add(TEXT("RootBalance"),TEXT("INPUT"),TEXT("Root self-balancing"),FString::Printf(TEXT("frequency %.3g damping %.3g max speed %.3g m/s"),B->frequency_hz,B->damping_ratio,B->maximum_speed));
    if(S.bHasBridgeIntent)R.Add(TEXT("Bridge"),TEXT("INPUT"),TEXT("Simulation bridge intent"),TEXT("external movement/steering intent"));
    if(S.AnimationLayer.IsActive() && S.AnimationLayer.BlendWeight>0)
        R.Add(TEXT("AnimLayer"),TEXT("POSE+HISTORY"),TEXT("Authored animation layer"),FString::Printf(TEXT("%s | weight %.3f bone mask 0x%x"),*GetNameSafe(S.AnimationLayer.Animation.Get()),S.AnimationLayer.BlendWeight,S.AnimationLayer.BoneMask));
    if(R.Attack)
    {
        R.Add(TEXT("AttackTiming"),TEXT("STATE"),TEXT("Attack phase / end"),FString::Printf(TEXT("policy frame %d | Hit frame %d | latched tail %d"),Slash.Frame,Slash.HitFrame,Slash.TailSteps));
        bool Parry=false,Dodge=false;GetAgentAttackDefenseState(A->GetAgentHandle(),Parry,Dodge);
        if(Parry||Dodge)R.Add(TEXT("AttackResponse"),TEXT("INPUT"),TEXT("Defender response conditioning"),FString::Printf(TEXT("parry %d dodge %d"),Parry,Dodge));
        R.Add(TEXT("AttackTarget"),TEXT("INPUT"),TEXT("Attack target conditioning"),FString::Printf(TEXT("requested %s | %s"),*Slash.TargetWorld.ToCompactString(),R.Half?TEXT("real-pelvis radius clamp, mapped to ghost carrier"):TEXT("anchored attack frame")));
        if(ProphecyAttackControls::IsStatic(A))R.Add(TEXT("StaticAttack"),TEXT("INPUT+HISTORY"),TEXT("Static attack history"),TEXT("previous state replaced by current"));
        if(ProphecyAttackControls::ArmedBlocked(A))R.Add(TEXT("ArmedBlock"),TEXT("INPUT"),TEXT("Armed transition blocked"));
        if(R.Half)
        {
            R.Add(TEXT("HalfMount"),TEXT("POSE"),TEXT("Half-attack upper mount"),FString::Printf(TEXT("spine compensation %d distributed %d position %d | target radius %.3g cm"),
                ProphecyHalfAttackCompensation::Enabled(A),ProphecyHalfAttackCompensation::Distributed(A),ProphecyHalfAttackCompensation::Position(A),GetHalfAttackTargetRadius(GetWorld())));
        }
        float Limit;bool Sword,Left;
        if(ProphecyAttackEndExtension::Threshold(A,Slash.Family,Limit,Sword,Left))
            R.Add(TEXT("EndExtension"),TEXT("GATE"),TEXT("Attack end angle extension"),FString::Printf(TEXT("%.3g degrees | %s | checked at end boundary"),Limit,Sword?TEXT("sword"):Left?TEXT("left hand"):TEXT("right hand")));
        if(ProphecyArmCone::AnyActive() && ProphecyArmCone::Active(A))
            R.Add(TEXT("ArmCone"),R.Half?TEXT("POSE"):TEXT("POSE+HISTORY"),TEXT("Arm repellant cone / wrist recoil"),TEXT("active attack constraint"));
        if(ProphecySpecialStart::Enabled(A) && Slash.Frame<=2)
            R.Add(TEXT("PhysicalSeed"),TEXT("ENTRY"),TEXT("Physical special-entry seed"),TEXT("enabled at entry; sampling availability determines whether physical pose replaced history"));
    }
    if(R.Attack || R.Defense)
    {
        if(ProphecySpecialRoll::Forearms(A))R.Add(TEXT("ForearmRoll"),TEXT("POSE"),TEXT("Forearm roll convention"),TEXT("UE canonical roll (attack motion filter may also encode it into history)"));
        if(!R.Half && ProphecySpecialRoll::Calves(A))R.Add(TEXT("CalfRoll"),TEXT("POSE"),TEXT("Calf roll convention"),TEXT("UE thigh-aligned calf frame"));
        const auto Mode=R.Attack?EProphecyClampProfileMode::Attack:R.Dodge?EProphecyClampProfileMode::Dodge:EProphecyClampProfileMode::Parry;
        const float Wrist=ProphecyAttackWrist::Degrees(A,Mode,R.Attack?Slash.Family:NAME_None);
        if(Wrist>=0 && Wrist<180)R.Add(TEXT("WristBend"),TEXT("CONSTRAINT"),TEXT("Left wrist bend limit"),FString::Printf(TEXT("%.3f degrees"),ProphecyClampEase::Current(A,ProphecyClampEase::EChannel::Wrist,Wrist)));
    }
    if(!ProphecyAttackWrist::FreePosition(A))
        R.Add(TEXT("FixedArms"),TEXT("CONSTRAINT"),TEXT("Fixed forearm attachment"),TEXT("wrists placed at authored forearm length after decoding"));
    bool Foot=A->bOverrideLocomotionFootClamp?A->bLocomotionFootClamp:bClampFoot;
    bool Calf=A->bOverrideLocomotionCalfClamp?A->bLocomotionCalfClamp:bClampCalf;
    float FL=A->bOverrideLocomotionFootClamp?A->LocomotionFootClampLeewayCm:0;
    float CL=A->bOverrideLocomotionCalfClamp?A->LocomotionCalfClampLeewayCm:0;
    if(R.Attack&&!R.Half)
    {
        Foot=A->bOverrideAttackFootClamp?A->bAttackFootClamp:bClampFoot;
        Calf=A->bOverrideAttackCalfClamp?A->bAttackCalfClamp:bClampCalf;
        FL=A->bOverrideAttackFootClamp?A->AttackFootClampLeewayCm:0;
        CL=A->bOverrideAttackCalfClamp?A->AttackCalfClampLeewayCm:0;
    }
    if(R.Defense)
    {
        const auto* D=ProphecyDefenseControls::Find(A,R.Dodge);
        Foot=D&&D->Foot.bOverride&&D->Foot.bEnabled;Calf=D&&D->Calf.bOverride&&D->Calf.bEnabled;
        if(D){FL=D->Foot.LeewayCm;CL=D->Calf.LeewayCm;}
    }
    const float Kick=ProphecyKickFootLeeway::Current(A);
    if(Kick>0){Foot=Calf=false;R.Add(TEXT("KickLeeway"),TEXT("POSE+PHYSICS"),TEXT("Kick leg leeway"),FString::Printf(TEXT("%.3f cm; ordinary leg clamps bypassed"),Kick));}
    if(Foot)R.Add(TEXT("FootClamp"),TEXT("CONSTRAINT"),TEXT("Foot reach clamp"),FString::Printf(TEXT("leeway %.3f cm"),ProphecyClampEase::Current(A,ProphecyClampEase::EChannel::Foot,FL)));
    if(Calf)R.Add(TEXT("CalfClamp"),TEXT("CONSTRAINT"),TEXT("Calf length clamp"),FString::Printf(TEXT("leeway %.3f cm"),ProphecyClampEase::Current(A,ProphecyClampEase::EChannel::Calf,CL)));
    if(ProphecyKickFootLeeway::HasLengthReturn(A))
        R.Add(TEXT("CalfReturn"),TEXT("POSE+PHYSICS"),TEXT("Calf length return"),FString::Printf(TEXT("weight %.3f | delta L %.3f R %.3f cm"),ProphecyKickFootLeeway::LengthReturnWeight(A),ProphecyKickFootLeeway::ReturningLengthDeltaCm(A,0),ProphecyKickFootLeeway::ReturningLengthDeltaCm(A,1)));
    if(R.LowerLoco)R.Add(TEXT("NativeFeet"),TEXT("CODEC"),TEXT("Foot contacts / toe roll"),FString::Printf(TEXT("pin L %.3f R %.3f | integration %d steps; geometry projection/rotation normalization"),S.PinProbability.X,S.PinProbability.Y,FootRollIntegrationSteps));
    if(A->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic || (A->bManualNNPoseApplication && A->GetPoseReferenceMesh() && A->GetPoseReferenceMesh()->IsAnySimulatingPhysics()))
    {
        R.Add(TEXT("Physics"),TEXT("PHYSICS"),TEXT("Physical pose"),FString::Printf(TEXT("%s | mode %d MACD %d | contact, gravity, joint limits, drive and external forces"),A->IsJoltPhysicalAnimationEnabled()?TEXT("Jolt"):TEXT("Chaos"),int32(A->GetSimulationMode()),A->IsMACDEnabled()));
        R.Add(TEXT("Feedback"),TEXT("HISTORY"),TEXT("Physical locomotion feedback"),R.Dodge?TEXT("bypassed during dodge"):
            FString::Printf(TEXT("last sample %s; tolerances below are deadbands; attack uses separate recurrence"),S.bHasPhysicalSample?TEXT("valid"):TEXT("not yet available")));
        if(!R.Dodge)for(const auto& Pair:S.PhysicalFeedbackTolerances)
        {
            const FString Name=Pair.Key.ToString();
            R.Add(*(TEXT("Feedback/")+Name),TEXT("HISTORY"),*(TEXT("Feedback ")+Name),FString::Printf(TEXT("linear %.3g cm | angular %.3g deg"),Pair.Value.LinearCm,Pair.Value.AngularDegrees));
        }
    }
    R.Add(TEXT("Interpolation"),TEXT("PRESENT"),TEXT("NN interpolation"),FString::Printf(TEXT("mode %d | interpolation %d | interval %.5g | manual application %d"),int32(A->GetNNInterpolationMode()),Interpolate,Interval,A->bManualNNPoseApplication));
    return true;
}
