"""Draft only. Extract the existing pose math verbatim; never write active source."""
import datetime, difflib, hashlib, json
from pathlib import Path
here=Path(__file__).resolve().parent
root=here.parents[2]
cpp_name='Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp'
h_name='Source/GameAnimationSample3/Public/ProphecyNNLocomotionManager.h'
kernel_name='Source/GameAnimationSample3/Private/ProphecyNNPoseBuild.inl'
test_name='Source/GameAnimationSample3/Private/Tests/ProphecyNNPoseBuildTests.inl'
raw={name:(root/name).read_bytes() for name in (cpp_name,h_name)}
cpp=raw[cpp_name].decode().replace('\r\n','\n'); header=raw[h_name].decode().replace('\r\n','\n')
function_start=cpp.index('void AProphecyNNLocomotionManager::PublishAgentPose(')
function_end=cpp.index('\nvoid AProphecyNNLocomotionManager::UpdateVisualRoots()',function_start)
original=cpp[function_start:function_end]
lambda_start=original.index('\tauto BuildFullPoseTransforms =')
body_start=original.index('\t{\n',lambda_start)+len('\t{\n')
body_end=original.index('\n\t};',body_start)
body='\n'.join(line[1:] if line.startswith('\t') else line for line in original[body_start:body_end].splitlines())
kernel=(here/'KernelPrefix.txt').read_text()+body+'\n}\n\n'+(here/'KernelSuffix.txt').read_text()
finish_start=original.index('\tApplySlashPose(AgentIndex, PreviousComponentTransforms, ComponentTransforms);')
finish=original[finish_start:]
new_methods='''void AProphecyNNLocomotionManager::PublishAgentPose(int32 AgentIndex, double SourceTimeSeconds)
{
    ProphecyJolt::CharacterProfiling::FScope Timing(ProphecyJolt::CharacterProfiling::EPhase::ManagerPosePublish);
    const FPublishedPoseGeometry Geometry = CapturePublishedPoseGeometry(*Impl);
    const FPublishedPoseSettings Settings { bClampFoot, bClampCalf, FootClampLengthMultiplier, CalfClampLengthMultiplier };
    BuildPublishedPoseWork(Geometry, Settings, CapturePublishedPoseWork(*Impl, AgentIndex));
    FinishAgentPosePublication(AgentIndex, SourceTimeSeconds);
}

void AProphecyNNLocomotionManager::PublishAgentPoseBatch(double SourceTimeSeconds)
{
    check(IsInGameThread());
    // No publication callbacks occur in the build. Borrowed input/layout views stay immutable
    // until the joined batch returns; all UObject, slash and store work remains below on GT.
    const FPublishedPoseGeometry Geometry = CapturePublishedPoseGeometry(*Impl);
    const FPublishedPoseSettings Settings { bClampFoot, bClampCalf, FootClampLengthMultiplier, CalfClampLengthMultiplier };
    TArray<FPublishedPoseWork, TInlineAllocator<BatchSize>> Work;
    Work.Reserve(CrowdSize);
    for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
        Work.Add(CapturePublishedPoseWork(*Impl, AgentIndex));
    BuildPublishedPoseBatch(Geometry, Settings, MakeArrayView(Work));
    for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
    {
        // StoreSeconds encloses the build plus these ordered commits. This per-agent scope
        // measures only GT publication when the opt-in batch path is selected.
        ProphecyJolt::CharacterProfiling::FScope Timing(ProphecyJolt::CharacterProfiling::EPhase::ManagerPosePublish);
        FinishAgentPosePublication(AgentIndex, SourceTimeSeconds);
    }
}

void AProphecyNNLocomotionManager::FinishAgentPosePublication(int32 AgentIndex, double SourceTimeSeconds)
{
    check(IsInGameThread());
    FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
    Agent.PublishedPoseTimeSeconds = SourceTimeSeconds;
    TArrayView<FTransform> LocalTransforms = TransformSlice(Impl->LocalTransformBuffer, AgentIndex);
    TArrayView<FTransform> PreviousComponentTransforms = TransformSlice(Impl->PreviousComponentTransformBuffer, AgentIndex);
    TArrayView<FTransform> ComponentTransforms = TransformSlice(Impl->ComponentTransformBuffer, AgentIndex);
'''+finish
cpp=cpp[:function_start]+new_methods+cpp[function_end:]
needle='#include "ProphecyNNPhysicalFeedbackBatch.inl"\n'
assert cpp.count(needle)==1
cpp=cpp.replace(needle,needle+'\n'+kernel+'\n')
needle='#include "Tests/ProphecyNNPhysicalFeedbackBatchTests.inl"\n'
assert cpp.count(needle)==1
cpp=cpp.replace(needle,needle+'\n'+(here/'TestBody.txt').read_text()+'\n')
needle='''		for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
		{
			PublishAgentPose(AgentIndex, PoseSourceTime);
		}
		if (bWarmed) Impl->Stats.StoreSeconds += FPlatformTime::Seconds() - Start;'''
replacement='''		static const bool bParallelPoseBuild = FParse::Param(FCommandLine::Get(), TEXT("ProphecyNNParallelPoseBuild"));
		if (bParallelPoseBuild)
		{
			PublishAgentPoseBatch(PoseSourceTime);
		}
		else
		{
			for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
				PublishAgentPose(AgentIndex, PoseSourceTime);
		}
		if (bWarmed) Impl->Stats.StoreSeconds += FPlatformTime::Seconds() - Start;'''
assert cpp.count(needle)==1
cpp=cpp.replace(needle,replacement)
needle='\tvoid PublishAgentPose(int32 AgentIndex, double SourceTimeSeconds);\n'
assert header.count(needle)==1
header=header.replace(needle,needle+'\tvoid PublishAgentPoseBatch(double SourceTimeSeconds);\n\tvoid FinishAgentPosePublication(int32 AgentIndex, double SourceTimeSeconds);\n')
files={cpp_name:cpp,h_name:header}
patch=[]
for name,contents in files.items():
    destination=here/name; destination.parent.mkdir(parents=True,exist_ok=True)
    assert destination.resolve().is_relative_to(here)
    with destination.open('w',encoding='utf-8',newline='\n') as stream:stream.write(contents)
    before=raw.get(name,b'').decode().replace('\r\n','\n')
    patch.extend(difflib.unified_diff(before.splitlines(True),contents.splitlines(True),fromfile='a/'+name if name in raw else '/dev/null',tofile='b/'+name))
with (here/'Proposed.patch').open('w',encoding='utf-8',newline='\n') as stream:stream.write(''.join(patch))
sha=lambda value:hashlib.sha256(value).hexdigest().upper()
evidence={'status':'DRAFT_ONLY_NOT_COMPILED_OR_RUN','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'baseline_hashes':{name:sha(data) for name,data in raw.items()},'draft_hashes':{name:sha(contents.encode()) for name,contents in files.items()},
 'original_math_body_sha256_after_one_tab_dedent':sha(body.encode()),
 'scope':'Default remains serial. Only opt-in outer 30Hz store-loop builds are parallel; initialization, slash/catch-up and root-correction callers remain serial. No active source writes.'}
with (here/'Baseline.json').open('w',encoding='utf-8') as stream:json.dump(evidence,stream,indent=2)
print(json.dumps({'files':len(files),'patch_lines':len(''.join(patch).splitlines()),'baseline':evidence['baseline_hashes']}))
