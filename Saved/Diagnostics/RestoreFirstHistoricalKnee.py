import pathlib,subprocess
root=pathlib.Path.cwd();src=root/'Source/GameAnimationSample3/Private';saved=root/'Saved/Diagnostics/SupportSourceExperiments'
for name in ('ProphecyLowerTempering.inl','ProphecyNNLocomotionManager.cpp','ProphecyHarnessKneeTrial.inl'):
 (saved/('BeforeUserHistoricalRestore-'+name)).write_bytes((src/name).read_bytes())
# All manager changes since HEAD were audited: Run boost is independent and retained.
manager=subprocess.check_output(['git','show','HEAD:Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp']).decode('utf-8')
marker='\t\t\tconst bool bTransfer=PinTransferMultiplier>0 && bWalkPolicy && bVisiblePolicy;'
assert manager.count(marker)==1
manager=manager.replace(marker,'            // Apply after the existing Run floor boost, before foot-roll correction.\n            // RawPin remains the decoded network value; EffectivePin includes this change.\n            if(!bWalkPolicy) ProphecyWalkPinning::BoostRunPin(PinActor,Pin[0],Pin[1]);\n'+marker)
(src/'ProphecyNNLocomotionManager.cpp').write_text(manager,encoding='utf-8')
# Restore exactly the first historical trial (September20 mode7), independent of editor cvars.
path=src/'ProphecyLowerTempering.inl';text=path.read_text(encoding='utf-8')
start=text.index('#include "ProphecyHarnessKneeTrial.inl"')
end=text.index('#if WITH_DEV_AUTOMATION_TESTS',start)
old=(saved/'September25-trials-ProphecyKneeHistoricalAudit.inl').read_text(encoding='utf-8')
body=old[old.index('void ResolveTemperedLegSeptember20'):old.rfind('\n#endif')]
body=body.replace('ResolveTemperedLegSeptember20','ResolveTemperedLeg').replace('const float* ExperimentNNSource=nullptr,int32 ExperimentMode=7)','const float* ExperimentNNSource=nullptr)')
body=body.replace('{\n    const FVector3f Pelvis','{\n    constexpr int32 ExperimentMode=7; // Exact first September20 comparison, selected by user.\n    const FVector3f Pelvis',1)
body=body.replace('#if WITH_EDITOR\n','').replace('#endif\n','')
text=text[:start]+body+'\n'+text[end:]
text=text.replace('static TAutoConsoleVariable<int32> CVarRecoveryCleanSource(TEXT("Prophecy.Recovery.CleanSource"),1,\n    TEXT("Editor comparison: 1 preserves the untouched NN hinge during calf/regional recovery; 0 uses the old post-pin source."));\n','')
path.write_text(text,encoding='utf-8')
(src/'ProphecyHarnessKneeTrial.inl').unlink()
print('Restored first historical solver; removed harness trial and subsequent clean-source change; Run boost retained')
