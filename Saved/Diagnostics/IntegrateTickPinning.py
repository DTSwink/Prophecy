from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp');s=p.read_text().replace('#include "ProphecyWalkPinning.h"','#include "ProphecyWalkPinning.h"\n#include "ProphecyWalkTickPinning.h"')
s=s.replace('\tUpdateVisualRoots();\n\tProphecyRootPelvisBounds', '\tUpdateVisualRoots();\n    if(ProphecyWalkPinning::AnyTickPinning()) UpdateWalkTickPinning();\n\tProphecyRootPelvisBounds')
s=s.replace('\t\tconst bool bWalkPolicy = !Agent.RecoveryWeights.NeedsRun();','''        auto* TickPins=PinSmoothing && !Agent.DefensePose && !Agent.Slash.bActive && Agent.RecoveryWeights.NeedsWalk()
            ? ProphecyWalkPinning::FindTickPinning(AgentActors[AgentIndex]) : nullptr;
        if(TickPins) {TickPins->Previous=TickPins->Current;TickPins->Current={};TickPins->Current.Valid=true;}
\t\tconst bool bWalkPolicy = !Agent.RecoveryWeights.NeedsRun();''',1)
needle='\t\t\tfor (int32 LimbIndex = 0; LimbIndex < 2; ++LimbIndex)\n\t\t\t{\n\t\t\t\tconst FVector3f PredPos'
s=s.replace(needle,'''            if(TickPins && bWalkPolicy && bVisiblePolicy)
            {
                auto& T=TickPins->Current;FVector2f BackCaps(1,1);
                for(int32 I=0;I<2;++I)
                {
                    const FVector Foot=LowerPointToWorld(ReadStateVec3(CurrentState,PosOffsets[I]),Impl->SeedRootRot,Agent.FedInputRoot,Agent.FedInputYaw);
                    if(PinBackwardBound) BackCaps[I]=ProphecyWalkPinning::BoundPin(1.f,*PinBackwardBound,Foot,BoundRoot,BoundForward);
                    T.Cap[I]=PinCircleBound?ProphecyWalkPinning::CircleBoundPin(BackCaps[I],*PinCircleBound,Foot,CircleRoot):BackCaps[I];
                }
                if(bTransfer) T.Minimum=FVector2f(FMath::Clamp((1.f-BackCaps.Y)*PinTransferMultiplier,0.f,1.f),FMath::Clamp((1.f-BackCaps.X)*PinTransferMultiplier,0.f,1.f));
            }
'''+needle,1)
s=s.replace('\t\t\t\t\tOutPos = FMath::Lerp(PredPos, PinnedPos, Pin[LimbIndex]);','''                    if(TickPins && bWalkPolicy && bVisiblePolicy) TickPins->Current.Delta[LimbIndex]=PinnedPos-PredPos;
\t\t\t\t\tOutPos = FMath::Lerp(PredPos, PinnedPos, Pin[LimbIndex]);''',1)
s=s.replace('\t\t\tEffectivePin = FVector2f(Pin[0], Pin[1]);','''\t\t\tEffectivePin = FVector2f(Pin[0], Pin[1]);
            if(TickPins && bWalkPolicy && bVisiblePolicy) TickPins->Current.Applied=EffectivePin;''',1)
s=s.replace('\t\t\t\tif (PinSmoothing) ProphecyWalkPinning::ClearSmoothedFoot(*PinSmoothing,I);','''\t\t\t\tif (PinSmoothing) ProphecyWalkPinning::ClearSmoothedFoot(*PinSmoothing,I);
                if(TickPins) {TickPins->Current.Cap[I]=0;TickPins->Current.Applied[I]=0;TickPins->Current.Delta[I]=FVector3f::ZeroVector;}''',1)
s=s.replace('\t\tAgent.PinProbability = EffectivePin;', '''        if(TickPins)
        {
            TickPins->Current.WalkWeight=Agent.RecoveryWeights.Legs();
            for(int32 I=0;I<2;++I) TickPins->Current.OtherPin[I]=EffectivePin[I]-TickPins->Current.Applied[I]*TickPins->Current.WalkWeight[I];
        }
\t\tAgent.PinProbability = EffectivePin;''',1)
needle='\t\tPresentationHandClamp, ForearmClamp);\n}'
s=s.replace(needle,'''\t\tPresentationHandClamp, ForearmClamp);
    if(auto* T=ProphecyWalkPinning::FindTickPinning(Controls))
    {
        if(!Agent.Slash.bActive && !Agent.DefensePose && T->Current.Valid && ProphecyWalkPinning::FindSmoothing(Controls))
        {
            T->PoseId=PoseStoreAgentBase+AgentIndex;T->HasBase=true;T->Dirty=true;
            for(int32 I=0;I<2;++I)
            {
                const auto& L=Impl->Limbs[I];const int32 B[]={L.Start,L.Mid,L.End,L.Toe};
                for(int32 J=0;J<4;++J){const int32 K=I*4+J;T->Bones[K]=B[J];T->BasePrevious[K]=PreviousComponentTransforms[B[J]];T->BaseCurrent[K]=ComponentTransforms[B[J]];}
            }
        }
    }
}
#include "ProphecyWalkTickPinningRuntime.inl"''',1)
p.write_text(s)
