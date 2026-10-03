from pathlib import Path
import hashlib,json

root=Path.cwd()
draft=root/'Saved/JoltMigration/EndpointCacheDraft'
relative=Path('Source/GameAnimationSample3/Private')
names=['ProphecyNNPhysicalTargetPose.h','ProphecyNNPhysicalTargetPose.cpp','ProphecyNNPhysicalTargetPoseTests.cpp']
active={name:(root/relative/name).read_text(encoding='utf-8-sig').replace('\r\n','\n') for name in names}
result=dict(active)
h=result[names[0]]
assert h.count('private:\n')==1
h=h.replace('private:\n','private:\n    friend class FEndpointCache;\n',1)
anchor='// Game-thread only. OutPrevious is intentionally not interpolated:'
assert h.count(anchor)==1
h=h.replace(anchor,(draft/'HeaderAddition.txt').read_text()+anchor,1)
result[names[0]]=h
cpp=result[names[1]]
cpp=cpp.replace('#include "ProphecyNNPoseTypes.h"', '#include "ProphecyNNPoseTypes.h"\n#include "ProphecyJoltCharacterProfiling.h"\n#include "Misc/CommandLine.h"\n#include "Misc/Parse.h"',1)
profile_scope='    ProphecyJolt::CharacterProfiling::FScope EndpointTiming(ProphecyJolt::CharacterProfiling::EPhase::TargetEndpointExpand);\n'
evaluate_start='    OutNames.Reset(); OutFuture.Reset(); OutPrevious.Reset();\n    if (!bInitialized'
assert cpp.count(evaluate_start)==1
cpp=cpp.replace(evaluate_start,profile_scope+evaluate_start,1)
anchor='bool BuildWorldPoses(const USkeletalMesh& Mesh, const UPhysicsAsset& PhysicsAsset,'
assert cpp.count(anchor)==1
cpp=cpp.replace(anchor,(draft/'ImplementationAddition.txt').read_text()+anchor,1)
result[names[1]]=cpp
test=result[names[2]]
assert test.count('#endif')==1
test=test.replace('#include "ProphecyNNPhysicalTargetPose.h"','#include <limits>\n\n#include "ProphecyNNPhysicalTargetPose.h"',1)
test=test.replace('#endif',(draft/'TestAddition.txt').read_text()+(draft/'NonFiniteTestAddition.txt').read_text()+'#endif',1)
result[names[2]]=test
for name,content in result.items():
 dest=draft/relative/name
 dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(content,encoding='utf-8',newline='\n')
agent='Source/GameAnimationSample3/Private/ProphecyAgent.cpp'
before=(root/agent).read_text(encoding='utf-8-sig').replace('\r\n','\n')
edits=[
('\t\tbool bInterpolatePose = true;\n\t};',
 '\t\tbool bInterpolatePose = true;\n\t\tmutable ProphecyNNPhysicalTargets::FEndpointCache PhysicalEndpointCache;\n\t};'),
('\tFNNPoseDataSource& Source = NNPoseDataSources.FindOrAdd(this);\n\tSource.AgentId = AgentId;',
 '\tFNNPoseDataSource& Source = NNPoseDataSources.FindOrAdd(this);\n\tif (Source.AgentId != AgentId) Source.PhysicalEndpointCache.Reset();\n\tSource.AgentId = AgentId;'),
('\t\tif (!ProphecyNNPhysicalTargets::BuildWorldPoses(*SkeletalMesh, *PhysicsAsset, Pose,\n\t\t\tBoneNames, FutureWorldTransforms, InterpolatedWorldTransforms))',
 '\t\tconst bool bBuiltEndpoints = ProphecyNNPhysicalTargets::IsEndpointCacheDisabledByCommandLine()\n\t\t\t? ProphecyNNPhysicalTargets::BuildWorldPoses(*SkeletalMesh, *PhysicsAsset, Pose,\n\t\t\t\tBoneNames, FutureWorldTransforms, InterpolatedWorldTransforms)\n\t\t\t: DataSource->PhysicalEndpointCache.BuildWorldPoses(*SkeletalMesh, *PhysicsAsset, Pose,\n\t\t\t\tBoneNames, FutureWorldTransforms, InterpolatedWorldTransforms);\n\t\tif (!bBuiltEndpoints)')]
after=before
patch=['*** Begin Patch','*** Update File: '+agent]
for old,new in edits:
 assert after.count(old)==1,old
 after=after.replace(old,new,1)
 patch.append('@@')
 patch.extend('-'+line for line in old.splitlines())
 patch.extend('+'+line for line in new.splitlines())
patch.append('*** End Patch')
(draft/'AgentEndpointCache.apply-patch.txt').write_text('\n'.join(patch)+'\n',encoding='utf-8')
# Verify literal previous implementation of both arithmetic paths and all pre-existing oracle tests survived.
for marker in ['bool FLayout::Evaluate(', 'bool BuildWorldPoses(']:
 old_tail=active[names[1]][active[names[1]].index(marker):]
 old_function=old_tail if marker.startswith('bool BuildWorldPoses') else old_tail[:old_tail.index('bool BuildWorldPoses(')]
 assert old_function.strip() in result[names[1]].replace(profile_scope,'',1)
original_tests=active[names[2]]
original_tests=original_tests[:original_tests.rfind('#endif')]
assert original_tests in result[names[2]].replace('#include <limits>\n\n','',1)
report={'active_baseline_sha256':{str(relative/name):hashlib.sha256((root/relative/name).read_bytes()).hexdigest() for name in names},
        'agent_sha256':hashlib.sha256((root/agent).read_bytes()).hexdigest(),
        'agent_unique_hunks':len(edits),'uncached_evaluator_math_and_prior_tests_unchanged':True,
        'only_evaluator_change_is_entry_profile_scope':True,
        'active_edits_or_builds':False}
(draft/'SourceVerification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
