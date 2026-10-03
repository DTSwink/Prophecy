from pathlib import Path
p=Path('Source/GameAnimationSample3/Private');d=Path('Saved/Diagnostics')
archive=d/'SupportSourceExperiments';archive.mkdir(exist_ok=True)
for name in ('ProphecyLowerTempering.inl','ProphecyKneeHistoricalAudit.inl','ProphecyNNPoseTypes.cpp','ProphecyRecoveryLegLength.h'):
 (archive/('September25-trials-'+name)).write_text((p/name).read_text(encoding='utf-8'),encoding='utf-8')
s=(d/'LowerTempering-before-history25.inl').read_text(encoding='utf-8')
needle='#endif\nstatic bool NeedsTemperedLegReconstruction'
assert s.count(needle)==1
s=s.replace(needle,'''static TAutoConsoleVariable<int32> CVarRecoveryCleanSource(TEXT("Prophecy.Recovery.CleanSource"),1,
    TEXT("Editor comparison: 1 preserves the untouched NN hinge during calf/regional recovery; 0 uses the old post-pin source."));
#endif
static bool NeedsTemperedLegReconstruction''')
(p/'ProphecyLowerTempering.inl').write_text(s,encoding='utf-8')
s=(p/'ProphecyNNPoseTypes.cpp').read_text(encoding='utf-8')
start=s.index('    TMap<int32,FKneeBendFrames> GRecoveryKneeBendFrames;');end=s.index('\t// Called only on publication/configuration',start)
s=s[:start]+s[end:]
s=s.replace('float Zone,\n        TMap<int32,FKneeBendFrames>& Storage=GKneeBendFrames)','float Zone)')
s=s.replace('auto& Frames=Storage.FindOrAdd(AgentId);','auto& Frames=GKneeBendFrames.FindOrAdd(AgentId);')
start=s.index('\tif (LowerCm.X>0 && LowerCm.Y>0)\n');end=s.index('\n}',start)
s=s[:start]+'''\tif (LowerCm.X>0 && LowerCm.Y>0) GRecoveryLegLengths.Add(AgentId,{UpperCm,LowerCm});
\telse GRecoveryLegLengths.Remove(AgentId);'''+s[end:]
for part in [
 '    if (!GRecoveryLegLengths.IsEmpty() && UseRecoveryKneeReference() && GRecoveryLegLengths.Contains(AgentId))\n        CaptureKneeBendFrames(AgentId,Snapshot,1.f,GRecoveryKneeBendFrames);\n',
 '    GRecoveryKneeBendFrames.Remove(AgentId);\n',
 '    GRecoveryKneeBendFrames.Reset();\n',
 '    FKneeBendFrames RecoveryBendFrames;\n',
 '        if(bRecovery && UseRecoveryKneeReference()) if(const auto* Frames=GRecoveryKneeBendFrames.Find(AgentId))\n            RecoveryBendFrames=*Frames;\n']:
 assert s.count(part)==1,part;s=s.replace(part,'')
s=s.replace('Recovery.Lower[Side],\n                Transforms[Thigh].TransformVectorNoScale(RecoveryBendFrames.LocalPole[Side]));','Recovery.Lower[Side]);')
assert 'RecoveryKnee' not in s
(p/'ProphecyNNPoseTypes.cpp').write_text(s,encoding='utf-8')
s=(p/'ProphecyRecoveryLegLength.h').read_text(encoding='utf-8')
s=s.replace('double Upper,double Lower,\n    const FVector& FallbackPole=FVector::ZeroVector)','double Upper,double Lower)')
start=s.index('    const double Radius=');end=s.index('\n    const FVector NewKnee=',start)
s=s[:start]+'    const FVector NewUpper=Axis*Along+Projected.GetSafeNormal()*FMath::Sqrt(FMath::Max(0.,Upper*Upper-Along*Along));'+s[end:]
(p/'ProphecyRecoveryLegLength.h').write_text(s,encoding='utf-8')
s=(p/'ProphecyNNLocomotionManager.cpp').read_text(encoding='utf-8')
old='''        bool bCleanRecoverySource=false;
#if WITH_EDITOR
        bCleanRecoverySource=(bReturnLengths || bRegional) && ProphecyLegChainDebug::IsEnabled(AgentActors[AgentIndex])
            && CVarRecoveryCleanSource.GetValueOnGameThread()!=0;
#endif'''
new='''        // Pinning/tempering modifies the ankle before reconstruction. Its source
        // hinge must still come from the untouched policy leg, including after
        // tempering retires while the signed calf-length return is continuing.
        bool bCleanRecoverySource=(bReturnLengths || bRegional) && ProphecyLegChainDebug::IsEnabled(AgentActors[AgentIndex]);
#if WITH_EDITOR
        if(bCleanRecoverySource) bCleanRecoverySource=CVarRecoveryCleanSource.GetValueOnGameThread()!=0;
#endif'''
assert s.count(old)==1;s=s.replace(old,new)
s=s.replace('#include "ProphecyKneeStanceTests.inl"','#include "ProphecyKneeStanceTests.inl"\n#include "ProphecyRecoverySourceTests.inl"')
(p/'ProphecyNNLocomotionManager.cpp').write_text(s,encoding='utf-8')
print('Trials archived; retained untouched-source correction only')
