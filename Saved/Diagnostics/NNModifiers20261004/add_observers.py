from pathlib import Path
root=Path('Source/GameAnimationSample3/Private')
entries={
'ProphecyFKReturnLibrary.cpp':r'''
void ProphecyNNModifierDebug::FKReturn(FReport& R)
{
    using namespace ProphecyFKReturn;
    if(!R.UpperLoco)return;
    const auto* S=Active.Find(R.Agent);const auto* P=TickPhases.Find(R.Agent);if(!S || !P)return;
    const auto W=S->Curve.Weights(float(P->Elapsed));
    R.Add(TEXT("FKReturn"),TEXT("POSE+HISTORY"),TEXT("Attack FK return / lab inertia"),
        FString::Printf(TEXT("NN %.3f | tick %llu/%llu | coeff %.3g | ease %.3g | hold %.3g%s"),
        P->Complete?1.f:W.NN,P->Ticks,P->Limit,S->Curve.Coefficient,S->Curve.Easing,S->Curve.AlphaHold,
        P->Complete?TEXT(" | previous endpoint still returning"):TEXT("")));
    FString Groups;
    for(int32 I=0;I<GroupCount;++I)Groups+=FString::Printf(TEXT("%s%.3g"),I?TEXT(","):TEXT(""),W.Momentum[I]);
    R.Add(TEXT("FKMomentum"),TEXT("POSE+HISTORY"),TEXT("FK retained momentum by group"),Groups);
}
''',
'ProphecyAttackMotionInertiaLibrary.cpp':r'''
void ProphecyNNModifierDebug::AttackMotion(FReport& R)
{
    using namespace ProphecyAttackMotionInertia;
    const auto* S=States.Find(R.Agent);if(!R.Attack || !S || !S->FilteringNow)return;
    R.Add(TEXT("AttackMotion"),TEXT("POSE+HISTORY"),TEXT("Attack motion inertia"),
        FString::Printf(TEXT("%s | response %.4g | Armed+%d ticks | %s"),
        S->Config.CoreOnly&&!S->SawHit?TEXT("core, no clavicles/arms"):TEXT("whole upper"),S->Config.Response,S->Config.After,
        S->SawHit?TEXT("after Hit"):S->SawArmed?TEXT("armed"):TEXT("pre-armed")));
}
''',
'ProphecyAttackStartFKCore.inl':r'''
void ProphecyNNModifierDebug::EntryCore(FReport& R)
{
    using namespace ProphecyAttackStartFKCore;
    const auto* S=States.Find(R.Agent);if(!R.Attack || !S)return;
    R.Add(TEXT("EntryCore"),TEXT("POSE+HISTORY"),TEXT("Attack-start FK core inertia"),
        FString::Printf(TEXT("weight %.3f | response %.3g | elapsed %.3f / %.3f%s"),Weight(S->Config,S->Elapsed),
        S->Config.Response,S->Elapsed,double(S->Config.Hold)+S->Config.Blend,S->Applied?TEXT(""):TEXT(" | entry seed, awaiting prediction")));
}
''',
'ProphecyAttackStartHandInertia.cpp':r'''
void ProphecyNNModifierDebug::EntryHands(FReport& R)
{
    using namespace ProphecyAttackStartHands;
    const auto* S=States.Find(R.Agent);if(!R.Attack || !S)return;
    R.Add(TEXT("EntryHands"),TEXT("POSE+HISTORY"),TEXT("Attack-start hand inertia"),
        FString::Printf(TEXT("L%d R%d | weight %.3f | response %.3g | root/spine ref %.3g | elapsed %.3f / %.3f%s"),
        S->Config.Hand[0],S->Config.Hand[1],Weight(S->Config,S->Elapsed),S->Config.Response,S->Config.Reference,
        S->Elapsed,double(S->Config.Hold)+S->Config.Blend,S->Applied?TEXT(""):TEXT(" | awaiting prediction")));
}
''',
'ProphecyPelvisInertiaLibrary.cpp':r'''
void ProphecyNNModifierDebug::PelvisInertia(FReport& R)
{
    using namespace ProphecyPelvisInertia;
    const auto* S=States.Find(R.Agent);if(!S || !S->Active())return;
    const bool Physical=BodyMode(R.Agent,*S);
    if(!Physical && !R.LowerLoco && !R.Attack)return;
    R.Add(TEXT("PelvisInertia"),Physical?TEXT("PHYSICS"):TEXT("POSE+HISTORY"),TEXT("Pelvis inertia"),
        FString::Printf(TEXT("linear %s | angular %s%s"),*S->Linear.ToCompactString(),*S->Angular.ToCompactString(),
        S->bSeeded||Physical?TEXT(""):TEXT(" | waiting for seed")));
}
''',
'ProphecyHandInertiaLibrary.cpp':r'''
void ProphecyNNModifierDebug::HandInertia(FReport& R)
{
    using namespace ProphecyHandInertia;
    // Current locomotion output deliberately bypasses the legacy hand filter.
    const auto* S=States.Find(R.Agent);if(!R.Attack || !S)return;
    for(int32 I=0;I<2;++I)
    {
        const auto& H=S->Hands[I];const auto F=Resolve(H,R.Walk,true);if(!Active(H,F))continue;
        R.Add(I?TEXT("HandInertiaR"):TEXT("HandInertiaL"),TEXT("POSE+HISTORY"),I?TEXT("Right hand inertia"):TEXT("Left hand inertia"),
            FString::Printf(TEXT("root-local linear %s | angular %s%s"),*F.Linear.ToCompactString(),*F.Angular.ToCompactString(),
            H.Seeded?TEXT(""):TEXT(" | waiting for seed")));
    }
}
''',
'ProphecyLowerTemperingLibrary.cpp':r'''
void ProphecyNNModifierDebug::Lower(FReport& R)
{
    if(!R.LowerLoco)return;
    using namespace ProphecyLowerTempering;
    if(const auto* S=Settings.Find(R.Agent))
    {
        if(S->PelvisTranslation!=1 || S->PelvisTranslationZ!=1 || S->PelvisRotation!=1)
            R.Add(TEXT("PelvisTempering"),TEXT("POSE+HISTORY"),TEXT("Pelvis tempering"),FString::Printf(TEXT("follow XY %.3f Z %.3f rotation %.3f"),S->PelvisTranslation,S->PelvisTranslationZ,S->PelvisRotation));
        const auto& Right=RightFootSettings(R.Agent,*S);
        for(int32 I=0;I<2;++I)
        {
            const auto& F=I?Right:*S;if(F.FeetAreIdentity())continue;
            R.Add(I?TEXT("FootTemperR"):TEXT("FootTemperL"),TEXT("POSE+HISTORY"),I?TEXT("Right foot tempering"):TEXT("Left foot tempering"),
                FString::Printf(TEXT("follow XY %.3f Z %.3f rotation %.3f"),F.FeetTranslation,F.FeetTranslationZ,F.FeetRotation));
        }
        if(Returns.Contains(R.Agent)||FeetReturns.Contains(R.Agent)||PelvisReturns.Contains(R.Agent))
            R.Add(TEXT("TemperReturn"),TEXT("STATE"),TEXT("Tempering blend to normal"),TEXT("finite return running; values above are the last accepted sample"));
    }
    if(const auto* S=ProphecyLegRecovery::Active.Find(R.Agent))
        R.Add(TEXT("KneeRecovery"),TEXT("POSE+HISTORY"),TEXT("Knee pole recovery"),FString::Printf(TEXT("%.3f / %.3g | pole speed %.3g deg/s"),S->Elapsed,S->Config.Duration,S->Config.Speed));
    if(ProphecyLegChainDebug::IsEnabled(R.Agent))
        R.Add(TEXT("LegReconstruction"),TEXT("CONSTRAINT"),TEXT("Leg chain reconstruction"),
            FString::Printf(TEXT("preserves accepted feet; knee/length solver, minimum reach x%.3g"),MinimumLegReachMultiplier(R.Agent)));
}
''',
'ProphecyAttackFootLocomotionLibrary.cpp':r'''
void ProphecyNNModifierDebug::Drag(FReport& R)
{
    using namespace ProphecyAttackFootLocomotion;
    if(!R.Attack || R.Half)return;
    if(const auto* D=FindActive(R.Agent))
    {
        R.Add(TEXT("LocoDrag"),TEXT("POSE+HISTORY"),TEXT("Attack loco drag"),FString::Printf(TEXT("loco feet mask %d | mode %d | release distance %.3g height %.3g"),D->Loco,int32(D->Config.Mode),D->Config.Distance,D->Config.Height));
        if(const auto* H=Handoffs.Find(R.Agent);H && H->Started)
            R.Add(TEXT("DragHandoff"),TEXT("POSE+HISTORY"),TEXT("Loco-drag foot handoff"),FString::Printf(TEXT("mask %d | L %.3f/%.3g R %.3f/%.3g | rotation %.3g"),H->Started,H->Elapsed[0],H->Config.Duration[0],H->Elapsed[1],H->Config.Duration[1],H->Config.Rotation));
        if(const auto* P=PoleBlends.Find(R.Agent);P && P->Feet)
            R.Add(TEXT("DragPole"),TEXT("POSE+HISTORY"),TEXT("Loco-drag knee pole blend"),FString::Printf(TEXT("feet mask %d | L %.3f R %.3f / %.3f"),P->Feet,P->Elapsed[0],P->Elapsed[1],P->Duration));
        if(FreezeWindows.Contains(R.Agent) && FreezeBlend(R.Agent)>0)
            R.Add(TEXT("DragFreeze"),TEXT("INPUT"),TEXT("Loco-drag frozen root window"),FString::Printf(TEXT("alpha %.3g"),FreezeBlend(R.Agent)));
    }
    if(FindGhost(R.Agent))
    {
        R.Add(TEXT("GhostLoco"),TEXT("INPUT+HISTORY"),TEXT("Ghost loco drag"),TEXT("undragged legs drive shared pelvis/upper recurrence; extra lower pass drives real legs"));
        if(const auto* G=GhostInertiaRuns.Find(R.Agent))
            R.Add(TEXT("GhostInertia"),TEXT("INPUT+HISTORY"),TEXT("Ghost loco inertia"),FString::Printf(TEXT("total %s cm | %.1f / %.1f ticks"),*G->Total.ToCompactString(),G->Elapsed*60.,G->Duration*60.));
    }
}
''',
'ProphecyForearmStretch.cpp':r'''
void ProphecyNNModifierDebug::Forearm(FReport& R)
{
    using namespace ProphecyForearmStretch;
    const auto* S=States.Find(R.Agent);if(!S)return;
    R.Add(TEXT("ForearmStretch"),TEXT("POSE+PHYSICS"),TEXT("Forearm length / wrist freedom"),
        S->Returning?FString::Printf(TEXT("return %llu/%llu ticks | weight %.3f | NN delta L %.3f R %.3f cm | physical delta L %.3f R %.3f cm"),
            S->Tick,S->Total,S->Weight(),S->Delta.X*S->Weight(),S->Delta.Y*S->Weight(),S->PhysicalDelta.X*S->Weight(),S->PhysicalDelta.Y*S->Weight())
        :TEXT("attack wrist translation free within trained +/-5 cm; arms follow NN stretch"));
}
''',
'ProphecyArmedPoseLibrary.cpp':r'''
void ProphecyNNModifierDebug::Armed(FReport& R)
{
    using namespace ProphecyArmedPose;
    const auto* S=States.Find(R.Agent);if(!S)return;
    const auto* B=Blends.Find(R.Agent);
    R.Add(TEXT("ManualArmed"),TEXT("POSE+HISTORY"),TEXT("Manual armed / GT pose"),FString::Printf(TEXT("%s | progress %.3f | %s | blend %.3f"),
        *S->Attack.ToString(),S->Alpha,S->Holding?TEXT("holding"):TEXT("moving"),B?BlendWeight(*B):1.));
    if(B)
    {
        FString Weights;for(int I=0;I<Count;++I)Weights+=FString::Printf(TEXT("%s%.2g"),I?TEXT(","):TEXT(""),B->Weights[I]);
        R.Add(TEXT("ArmedWeights"),TEXT("POSE+HISTORY"),TEXT("Manual pose joint weights"),Weights);
    }
}
''',
'ProphecyAttackStartInertiaLibrary.cpp':r'''
void ProphecyNNModifierDebug::Entry(FReport& R)
{
    using namespace ProphecyAttackStartInertia;
    {FReadScopeLock Guard(CorrectionLock);
    if(const auto* E=Entries.Find(R.Agent);E && Corrections.Contains(E->PoseId))
        R.Add(TEXT("EntryPelvis"),TEXT("PRESENT"),TEXT("Attack-start pelvis inertia"),FString::Printf(TEXT("tick %d | linear %.3f angular %.3f; reconstructed legs"),E->Frame,
            Weight(E->Frame,E->Config.LinearFrames,E->Config.Linear),Weight(E->Frame,E->Config.AngularFrames,E->Config.Angular)));}
    {FReadScopeLock Guard(Feet::Lock);
    if(const auto* P=Feet::Entries.Find(R.Agent))for(int32 I=0;I<2;++I)
    {
        const auto& E=P->Leg[I];const auto* T=Feet::Targets.Find(E.PoseId);if(!T || !(T->Active&(1<<I)))continue;
        R.Add(I?TEXT("EntryFootR"):TEXT("EntryFootL"),TEXT("PRESENT"),I?TEXT("Attack-start right foot inertia"):TEXT("Attack-start left foot inertia"),
            FString::Printf(TEXT("tick %d | linear %.3f angular %.3f"),E.Frame,Weight(E.Frame,E.Config.LinearFrames,E.Config.Linear),Weight(E.Frame,E.Config.AngularFrames,E.Config.Angular)));
    }}
}
''',
'ProphecyWalkPinningLibrary.cpp':r'''
void ProphecyNNModifierDebug::Pinning(FReport& R)
{
    using namespace ProphecyWalkPinning;
    if(!R.LowerLoco)return;
    if(const auto* S=Settings.Find(R.Agent))
        R.Add(TEXT("PinConflict"),TEXT("CONSTRAINT"),TEXT("Conflicting foot pin suppression"),FString::Printf(TEXT("tolerance %.3g fallback %.3g"),S->Tolerance,S->Fallback));
    if(const auto* B=BackwardBounds.Find(R.Agent))
        R.Add(TEXT("PinBackward"),TEXT("CONSTRAINT"),TEXT("Backward pin bound"),FString::Printf(TEXT("%.3g..%.3g cm | heading root %d"),B->MinCm,B->MaxCm,B->RootIndex));
    if(const auto* B=CircleBounds.Find(R.Agent))
        R.Add(TEXT("PinCircle"),TEXT("CONSTRAINT"),TEXT("Radial pin bound"),FString::Printf(TEXT("%.3g..%.3g cm"),B->MinCm,B->MaxCm));
    if(const auto* V=BackwardTransfers.Find(R.Agent);V && *V>0)
        R.Add(TEXT("PinTransfer"),TEXT("CONSTRAINT"),TEXT("Backward pin transfer"),FString::Printf(TEXT("multiplier %.3g"),*V));
    if(const auto* V=BackwardTargetLerps.Find(R.Agent);V && *V>0)
        R.Add(TEXT("PinHeading"),TEXT("INPUT"),TEXT("Pin bound target heading"),FString::Printf(TEXT("alpha %.3g"),*V));
    if(const auto* S=Smoothing.Find(R.Agent);S && S->Active())
        R.Add(TEXT("PinSmoothing"),TEXT("POSE+HISTORY"),TEXT("Foot pin smoothing"),FString::Printf(TEXT("L %.3f -> %.3f R %.3f -> %.3f | in %d out %d ticks"),S->Current[0],S->Target[0],S->Current[1],S->Target[1],S->InFrames,S->OutFrames));
    if(const auto* S=ReachGuards.Find(R.Agent))
        R.Add(TEXT("PinReach"),TEXT("CONSTRAINT"),TEXT("Foot pin reach rejection"),FString::Printf(TEXT("cooldown L%d R%d / %d ticks"),S->Remaining[0],S->Remaining[1],S->Frames));
    if(const auto* S=TickPins.Find(R.Agent);S && S->HasBase)
        R.Add(TEXT("TickPins"),TEXT("PRESENT"),TEXT("Game-tick pin smoothing"),FString::Printf(TEXT("effective L %.3f R %.3f"),S->Effective.X,S->Effective.Y));
}
''',
}
for name,code in entries.items():
    p=root/name;s=p.read_text(encoding='utf-8-sig');assert 'void ProphecyNNModifierDebug::' not in s,name
    # Header must precede inl includes sharing its types.
    if not s.startswith('#include "ProphecyNNModifierDebug.h"'):
        s='#include "ProphecyNNModifierDebug.h"\n'+s
    p.write_text(s+'\n'+code,encoding='utf-8')
print('added observers:',len(entries))
