import pathlib, hashlib, difflib, json

ROOT = pathlib.Path(__file__).resolve().parents[3]
DRAFT = pathlib.Path(__file__).resolve().parent
FILES = {}

def read(rel):
    text = (ROOT / rel).read_text(encoding='utf-8-sig')
    FILES[rel] = text
    return text

def once(text, old, new):
    assert text.count(old) == 1, (old[:100], text.count(old))
    return text.replace(old, new)

def save(rel, text):
    target = DRAFT / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8', newline='\n')

M = 'Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp'
manager = read(M)
start = manager.index('bool AProphecyNNLocomotionManager::ResamplePhysicalAgentState(int32 AgentIndex)')
end = manager.index('\nvoid AProphecyNNLocomotionManager::BuildInputBatch', start)
original = manager[start:end]
math_start = original.index('\tfloat* Sample = StateSlice')
legacy_math = original[math_start:original.rfind('\n}')]
legacy_math = legacy_math.replace('Impl->', 'Impl.').replace('*Impl', 'Impl')
legacy = ('bool CommitPhysicalSampleSerial(AProphecyNNLocomotionManager::FImpl& Impl, int32 AgentIndex,\n'
          '    TConstArrayView<FTransform> ActualTransforms)\n{\n'
          '    using FImpl = AProphecyNNLocomotionManager::FImpl;\n' + legacy_math + '\n}\n')

work_type = '''
	// Native work records are prepared on GT. Workers touch only their own record
	// and fixed agent-index output slices; the model/layout data is read-only.
	struct FPhysicalFeedbackWorkItem
	{
		TConstArrayView<FTransform> ActualTransforms;
		float* Sample = nullptr;
		float* Previous = nullptr;
		float* Current = nullptr;
		float* PreviousPhysical = nullptr;
		float* UpperSample = nullptr;
		float* UpperCurrent = nullptr;
		float* UpperPrevious = nullptr;
		float* UpperPreviousPhysical = nullptr;
		float* UpperCurrentBase = nullptr;
		float* PreviousPelvisHeading = nullptr;
		float* CurrentPelvisHeading = nullptr;
		FPhysicalFeedbackTolerance LowerTolerances[7];
		FPhysicalFeedbackTolerance UpperCoreTolerances[10];
		FPhysicalFeedbackTolerance UpperEndTolerances[2];
		FPhysicalFeedbackTolerance UpperStartTolerances[2];
		bool bUseWalkPolicy = false;
		bool bHasPhysicalSample = false;
		bool bSucceeded = false;
	};
	TArray<FPhysicalFeedbackWorkItem> PhysicalFeedbackWorkItems;
	TArray<int32> PhysicalFeedbackIndices;
	uint64 PreparedPhysicalSamples = 0;
	uint64 PreparedPhysicalBatches = 0;
'''
manager = once(manager, '\tuint64 FailedPhysicalSamples = 0;', '\tuint64 FailedPhysicalSamples = 0;' + work_type)
manager = once(manager, '#include "ProphecyNNLocomotionManager.h"', '#include "ProphecyNNLocomotionManager.h"\n#include "Async/ParallelFor.h"')

# Retain the Agent overload for the existing serial path and independent raw oracle.
old_signature = ('\tvoid EncodePhysicalLowerSample(const AProphecyNNLocomotionManager::FImpl& Impl,\n'
                 '\t\tconst AProphecyNNLocomotionManager::FImpl::FAgent& Agent,\n')
manager = once(manager, old_signature, '\tvoid EncodePhysicalLowerSample(const AProphecyNNLocomotionManager::FImpl& Impl,\n\t\tbool bUseWalkPolicy,\n')
raw_start = manager.index('\tvoid EncodePhysicalLowerSample(')
raw_end = manager.index('\n\tvoid EncodePhysicalUpperSample', raw_start)
raw = manager[raw_start:raw_end].replace('Agent.bUseWalkPolicy', 'bUseWalkPolicy')
raw += '''
	void EncodePhysicalLowerSample(const AProphecyNNLocomotionManager::FImpl& Impl,
		const AProphecyNNLocomotionManager::FImpl::FAgent& Agent,
		TConstArrayView<FTransform> ActualTransforms, FSampledTrainingRotations& TrainingRotations, float* Sample)
	{
		EncodePhysicalLowerSample(Impl, Agent.bUseWalkPolicy, ActualTransforms, TrainingRotations, Sample);
	}
'''
manager = manager[:raw_start] + raw + manager[raw_end:]
manager = once(manager, '#include "Tests/ProphecyNNPhysicalRotationCacheTests.inl"\n#endif', '#include "Tests/ProphecyNNPhysicalRotationCacheTests.inl"\n#endif\n\n#include "ProphecyNNPhysicalFeedbackBatch.inl"\n#if WITH_DEV_AUTOMATION_TESTS\n#include "Tests/ProphecyNNPhysicalFeedbackBatchTests.inl"\n#endif')

worker = legacy_math
worker = worker.replace('\tFImpl::FAgent& Agent = Impl.Agents[AgentIndex];\n', '')
worker = worker.replace('\tconst double RawEncodeStart = ProphecyJolt::CharacterProfiling::Timestamp();\n', '')
worker = worker.replace('\tProphecyJolt::CharacterProfiling::RecordElapsed(ProphecyJolt::CharacterProfiling::EPhase::PhysicalRawEncode, RawEncodeStart);\n', '')
worker = worker.replace('\t\tProphecyJolt::CharacterProfiling::FScope Timing(ProphecyJolt::CharacterProfiling::EPhase::PhysicalRawEncode);\n', '')
worker = worker.replace('EncodePhysicalLowerSample(Impl, Agent,', 'EncodePhysicalLowerSample(Impl, Work.bUseWalkPolicy,')
worker = worker.replace('Agent.bHasPhysicalSample', 'Work.bHasPhysicalSample')
pointers = {
    'StateSlice(Impl.PhysicalStateBuffer, AgentIndex)': 'Work.Sample',
    'StateSlice(Impl.PrevStateBuffer, AgentIndex)': 'Work.Previous',
    'StateSlice(Impl.CurStateBuffer, AgentIndex)': 'Work.Current',
    'StateSlice(Impl.PreviousPhysicalStateBuffer, AgentIndex)': 'Work.PreviousPhysical',
    'UpperStateSlice(Impl.UpperPhysicalStateBuffer, AgentIndex)': 'Work.UpperSample',
    'UpperStateSlice(Impl.UpperCurrentStateBuffer, AgentIndex)': 'Work.UpperCurrent',
    'UpperStateSlice(Impl.UpperPreviousStateBuffer, AgentIndex)': 'Work.UpperPrevious',
    'UpperStateSlice(\n\t\tImpl.UpperPreviousPhysicalStateBuffer, AgentIndex)': 'Work.UpperPreviousPhysical',
    'UpperStateSlice(Impl.UpperCurrentBaseBuffer, AgentIndex)': 'Work.UpperCurrentBase',
    'TransformStateSlice(Impl.PreviousPelvisHeadingBuffer, AgentIndex)': 'Work.PreviousPelvisHeading',
    'TransformStateSlice(Impl.CurrentPelvisHeadingBuffer, AgentIndex)': 'Work.CurrentPelvisHeading',
}
for old, new in pointers.items():
    worker = once(worker, old, new)
for i, name in enumerate(['pelvis', 'thigh_l', 'foot_l', 'ball_l', 'thigh_r', 'foot_r', 'ball_r']):
    worker = once(worker, 'FeedbackToleranceForBone(Agent, TEXT("' + name + '"))', f'Work.LowerTolerances[{i}]')
worker = worker.replace('(int32 Offset, FName BoneName)', '(int32 Offset, const FPhysicalFeedbackTolerance& Tolerance)')
worker = worker.replace('\t\tconst FPhysicalFeedbackTolerance& Tolerance = FeedbackToleranceForBone(Agent, BoneName);\n', '')
worker = once(worker, 'ApplyUpperAngularTolerance(CoreIndex * 6, Impl.UpperCoreBoneNames[CoreIndex]);', 'ApplyUpperAngularTolerance(CoreIndex * 6, Work.UpperCoreTolerances[CoreIndex]);')
worker = once(worker, '\t\tconst FImpl::FUpperArm& Arm = Impl.UpperArms[ArmIndex];\n', '')
worker = once(worker, 'ApplyUpperLinearTolerance(Offset, Impl.BodyNames[Arm.End]);', 'ApplyUpperLinearTolerance(Offset, Work.UpperEndTolerances[ArmIndex]);')
worker = once(worker, 'ApplyUpperAngularTolerance(Offset + 3, Impl.BodyNames[Arm.End]);', 'ApplyUpperAngularTolerance(Offset + 3, Work.UpperEndTolerances[ArmIndex]);')
worker = once(worker, 'ApplyUpperAngularTolerance(Offset + 9, Impl.BodyNames[Arm.Start]);', 'ApplyUpperAngularTolerance(Offset + 9, Work.UpperStartTolerances[ArmIndex]);')
assert 'AgentIndex' not in worker and 'FeedbackToleranceForBone' not in worker and 'CharacterProfiling' not in worker
kernel = '''// Included in the manager's anonymous namespace after the native math helpers.
// The serial reference preserves the previous operation order and GT profiling.
''' + legacy + '''
bool CommitPreparedPhysicalSample(const AProphecyNNLocomotionManager::FImpl& Impl,
    AProphecyNNLocomotionManager::FImpl::FPhysicalFeedbackWorkItem& Work)
{
    using FImpl = AProphecyNNLocomotionManager::FImpl;
    const TConstArrayView<FTransform> ActualTransforms = Work.ActualTransforms;
''' + worker + '''
}

bool PreparePhysicalFeedbackWork(AProphecyNNLocomotionManager::FImpl& Impl, int32 AgentIndex)
{
    check(IsInGameThread());
    if (!Impl.Agents.IsValidIndex(AgentIndex) || !Impl.PhysicalFeedbackWorkItems.IsValidIndex(AgentIndex)
        || Impl.UpperCoreBoneNames.Num() != 10) return false;
    auto& Work = Impl.PhysicalFeedbackWorkItems[AgentIndex];
    const auto& Agent = Impl.Agents[AgentIndex];
    Work = {};
    Work.ActualTransforms = TransformSlice(Impl.PhysicalTransformBuffer, AgentIndex);
    Work.Sample = StateSlice(Impl.PhysicalStateBuffer, AgentIndex);
    Work.Previous = StateSlice(Impl.PrevStateBuffer, AgentIndex);
    Work.Current = StateSlice(Impl.CurStateBuffer, AgentIndex);
    Work.PreviousPhysical = StateSlice(Impl.PreviousPhysicalStateBuffer, AgentIndex);
    Work.UpperSample = UpperStateSlice(Impl.UpperPhysicalStateBuffer, AgentIndex);
    Work.UpperCurrent = UpperStateSlice(Impl.UpperCurrentStateBuffer, AgentIndex);
    Work.UpperPrevious = UpperStateSlice(Impl.UpperPreviousStateBuffer, AgentIndex);
    Work.UpperPreviousPhysical = UpperStateSlice(Impl.UpperPreviousPhysicalStateBuffer, AgentIndex);
    Work.UpperCurrentBase = UpperStateSlice(Impl.UpperCurrentBaseBuffer, AgentIndex);
    Work.PreviousPelvisHeading = TransformStateSlice(Impl.PreviousPelvisHeadingBuffer, AgentIndex);
    Work.CurrentPelvisHeading = TransformStateSlice(Impl.CurrentPelvisHeadingBuffer, AgentIndex);
    const FName LowerNames[] = { TEXT("pelvis"), TEXT("thigh_l"), TEXT("foot_l"), TEXT("ball_l"),
        TEXT("thigh_r"), TEXT("foot_r"), TEXT("ball_r") };
    for (int32 Index = 0; Index < 7; ++Index)
        Work.LowerTolerances[Index] = FeedbackToleranceForBone(Agent, LowerNames[Index]);
    for (int32 Index = 0; Index < 10; ++Index)
        Work.UpperCoreTolerances[Index] = FeedbackToleranceForBone(Agent, Impl.UpperCoreBoneNames[Index]);
    for (int32 Index = 0; Index < 2; ++Index)
    {
        Work.UpperEndTolerances[Index] = FeedbackToleranceForBone(Agent, Impl.BodyNames[Impl.UpperArms[Index].End]);
        Work.UpperStartTolerances[Index] = FeedbackToleranceForBone(Agent, Impl.BodyNames[Impl.UpperArms[Index].Start]);
    }
    Work.bUseWalkPolicy = Agent.bUseWalkPolicy;
    Work.bHasPhysicalSample = Agent.bHasPhysicalSample;
    return true;
}

void ExecutePhysicalFeedbackBatch(const AProphecyNNLocomotionManager::FImpl& ReadOnlyLayout,
    TArrayView<AProphecyNNLocomotionManager::FImpl::FPhysicalFeedbackWorkItem> WorkItems,
    TConstArrayView<int32> Indices, bool bForceSerial)
{
    check(IsInGameThread());
    ParallelFor(TEXT("ProphecyNN.PhysicalFeedback"), Indices.Num(), 4,
        [&ReadOnlyLayout, WorkItems, Indices](int32 ItemIndex)
        {
            auto& Work = WorkItems[Indices[ItemIndex]];
            Work.bSucceeded = CommitPreparedPhysicalSample(ReadOnlyLayout, Work);
        }, bForceSerial ? EParallelForFlags::ForceSingleThread : EParallelForFlags::None);
}
'''
save('Source/GameAnimationSample3/Private/ProphecyNNPhysicalFeedbackBatch.inl', kernel)

# Preserve the original GT sampler and replace only its post-sample tail.
replacement = original[:math_start] + '\treturn CommitPhysicalSampleSerial(*Impl, AgentIndex, ActualTransforms);\n}\n'
manager = once(manager, original, replacement)
old_call = '\t\t\tif (ResamplePhysicalAgentState(AgentIndex)) ++Impl->CompletedPhysicalSamples;\n\t\t\telse ++Impl->FailedPhysicalSamples;'
new_call = '''			if (PhysicalFeedbackExecutionMode == 0)
			{
				if (ResamplePhysicalAgentState(AgentIndex)) ++Impl->CompletedPhysicalSamples;
				else ++Impl->FailedPhysicalSamples;
				continue;
			}
			if (!Impl->Agents.IsValidIndex(AgentIndex))
			{
				++Impl->FailedPhysicalSamples;
				continue;
			}
			bool bSampled = false;
			{
				ProphecyJolt::CharacterProfiling::FScope SampleTiming(ProphecyJolt::CharacterProfiling::EPhase::PhysicalSampleRead);
				bSampled = AgentActor->SampleActualComponentPose(Impl->PublishedBoneNames,
					TransformSlice(Impl->PhysicalTransformBuffer, AgentIndex));
			}
			bool bPrepared = false;
			if (bSampled)
			{
				ProphecyJolt::CharacterProfiling::FScope PrepareTiming(ProphecyJolt::CharacterProfiling::EPhase::PhysicalFeedbackPrepare);
				bPrepared = PreparePhysicalFeedbackWork(*Impl, AgentIndex);
			}
			if (bPrepared) Impl->PhysicalFeedbackIndices.Add(AgentIndex);
			else ++Impl->FailedPhysicalSamples;'''
manager = once(manager, old_call, new_call)
manager = once(manager, '\tProphecyJolt::CharacterProfiling::FScope Timing(ProphecyJolt::CharacterProfiling::EPhase::ManagerPhysicalResample);', '\tProphecyJolt::CharacterProfiling::FScope Timing(ProphecyJolt::CharacterProfiling::EPhase::ManagerPhysicalResample);\n\tImpl->PhysicalFeedbackIndices.Reset();')
join = '''
	if (PhysicalFeedbackExecutionMode != 0 && !Impl->PhysicalFeedbackIndices.IsEmpty())
	{
		{
			ProphecyJolt::CharacterProfiling::FScope JoinedTiming(ProphecyJolt::CharacterProfiling::EPhase::PhysicalFeedbackBatch);
			ExecutePhysicalFeedbackBatch(*Impl, Impl->PhysicalFeedbackWorkItems, Impl->PhysicalFeedbackIndices,
				PhysicalFeedbackExecutionMode == 1);
		}
		++Impl->PreparedPhysicalBatches;
		for (const int32 AgentIndex : Impl->PhysicalFeedbackIndices)
		{
			const auto& Work = Impl->PhysicalFeedbackWorkItems[AgentIndex];
			if (Work.bSucceeded)
			{
				Impl->Agents[AgentIndex].bHasPhysicalSample = Work.bHasPhysicalSample;
				++Impl->CompletedPhysicalSamples;
				++Impl->PreparedPhysicalSamples;
			}
			else ++Impl->FailedPhysicalSamples;
		}
	}
'''
marker = '\n}\n\nbool AProphecyNNLocomotionManager::ResamplePhysicalAgentState'
manager = once(manager, marker, join + marker)
manager = once(manager, '\tImpl->PhysicalTransformBuffer.SetNumUninitialized(BatchSize * FullBodyBoneCount);', '\tImpl->PhysicalTransformBuffer.SetNumUninitialized(BatchSize * FullBodyBoneCount);\n\tif (PhysicalFeedbackExecutionMode != 0)\n\t{\n\t\tImpl->PhysicalFeedbackWorkItems.SetNum(BatchSize);\n\t\tImpl->PhysicalFeedbackIndices.Reserve(BatchSize);\n\t}')
setter = '''bool AProphecyNNLocomotionManager::SetPhysicalFeedbackExecutionMode(int32 Mode)
{
	if (!IsInGameThread() || HasActorBegunPlay() || Mode < 0 || Mode > 2) return false;
	PhysicalFeedbackExecutionMode = Mode;
	return true;
}

'''
manager = once(manager, 'void AProphecyNNLocomotionManager::BeginPlay()', setter + 'void AProphecyNNLocomotionManager::BeginPlay()')
manager = once(manager, '\tOutStats.FailedPhysicalSamples = Impl->FailedPhysicalSamples;', '\tOutStats.FailedPhysicalSamples = Impl->FailedPhysicalSamples;\n\tOutStats.PhysicalFeedbackExecutionMode = PhysicalFeedbackExecutionMode;\n\tOutStats.PreparedPhysicalSamples = Impl->PreparedPhysicalSamples;\n\tOutStats.PreparedPhysicalBatches = Impl->PreparedPhysicalBatches;')
save(M, manager)

H = 'Source/GameAnimationSample3/Public/ProphecyNNLocomotionManager.h'
header = read(H)
header = once(header, '\tint32 FootRollSteps = 0;', '\tint32 FootRollSteps = 0;\n\tint32 PhysicalFeedbackExecutionMode = 0;\n\tuint64 PreparedPhysicalSamples = 0, PreparedPhysicalBatches = 0;')
header = once(header, '\tvirtual void BeginPlay() override;', '\t/** Native opt-in before BeginPlay: 0 original, 1 prepared serial, 2 prepared parallel. */\n\tbool SetPhysicalFeedbackExecutionMode(int32 Mode);\n\n\tvirtual void BeginPlay() override;')
header = once(header, '\tbool ResamplePhysicalAgentState(int32 AgentIndex);', '\tbool ResamplePhysicalAgentState(int32 AgentIndex);\n\tint32 PhysicalFeedbackExecutionMode = 0;')
save(H, header)
for rel, old, new in [
    ('Source/GameAnimationSample3/Private/ProphecyJoltCharacterProfiling.h', 'TargetEndpointExpand, Count', 'TargetEndpointExpand, PhysicalFeedbackPrepare, PhysicalFeedbackBatch, Count'),
    ('Source/GameAnimationSample3/Private/ProphecyJoltCharacterProfiling.cpp', 'TEXT("target_endpoint_expand") };', 'TEXT("target_endpoint_expand"), TEXT("physical_feedback_prepare"), TEXT("physical_feedback_batch_wall") };')]:
    save(rel, once(read(rel), old, new))

B = 'Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkNNJolt.cpp'
benchmark = read(B)
benchmark = once(benchmark, '#include "Misc/CommandLine.h"', '#include "Misc/CommandLine.h"\n#include "Misc/Parse.h"')
benchmark = once(benchmark, '    int32 ValidatedFrames = 0, FramesWithoutNNStep = 0;', '    int32 ValidatedFrames = 0, FramesWithoutNNStep = 0;\n    int32 PhysicalFeedbackMode = 0;')
benchmark = once(benchmark, '    Row->SetNumberField(TEXT("foot_roll_steps"), Stats.FootRollSteps);', '''    Row->SetNumberField(TEXT("foot_roll_steps"), Stats.FootRollSteps);
    Row->SetNumberField(TEXT("physical_feedback_mode"), Stats.PhysicalFeedbackExecutionMode);
    Row->SetNumberField(TEXT("prepared_physical_samples"), double(Stats.PreparedPhysicalSamples));
    Row->SetNumberField(TEXT("prepared_physical_batches"), double(Stats.PreparedPhysicalBatches));''')
benchmark = once(benchmark, '        || Manager->InitialPhysicalAgentCount != 0', '        || Manager->InitialPhysicalAgentCount != 0\n        || Stats.PhysicalFeedbackExecutionMode != State.PhysicalFeedbackMode\n        || (State.PhysicalFeedbackMode == 0 && (Stats.PreparedPhysicalSamples || Stats.PreparedPhysicalBatches))')
benchmark = once(benchmark, '    TSet<AProphecyAgent*> Expected;', '''    FString FeedbackModeText = TEXT("Original");
    FParse::Value(FCommandLine::Get(), TEXT("PhysicsBenchFeedbackMode="), FeedbackModeText);
    const int32 FeedbackMode = FeedbackModeText.Equals(TEXT("Original"), ESearchCase::IgnoreCase) ? 0
        : FeedbackModeText.Equals(TEXT("PreparedSerial"), ESearchCase::IgnoreCase) ? 1
        : FeedbackModeText.Equals(TEXT("PreparedParallel"), ESearchCase::IgnoreCase) ? 2 : INDEX_NONE;
    if (FeedbackMode == INDEX_NONE)
    { Error = TEXT("PhysicsBenchFeedbackMode must be Original, PreparedSerial or PreparedParallel."); return false; }
    TSet<AProphecyAgent*> Expected;''')
benchmark = once(benchmark, '    Manager->FinishSpawning(FTransform::Identity);', '''    if (!Manager->SetPhysicalFeedbackExecutionMode(FeedbackMode))
    { Error = TEXT("Could not set native physical feedback execution before manager BeginPlay."); return false; }
    Manager->FinishSpawning(FTransform::Identity);''')
benchmark = once(benchmark, '    Pending->Manager = Manager;', '    Pending->Manager = Manager;\n    Pending->PhysicalFeedbackMode = FeedbackMode;')
benchmark = once(benchmark, '    const uint64 Steps = Stats.CompletedNNSteps - Previous.CompletedNNSteps;', '''    if (Stats.PreparedPhysicalSamples < Previous.PreparedPhysicalSamples
        || Stats.PreparedPhysicalBatches < Previous.PreparedPhysicalBatches)
    { Error = TEXT("Prepared feedback counters moved backwards."); return false; }
    const uint64 Steps = Stats.CompletedNNSteps - Previous.CompletedNNSteps;''')
benchmark = once(benchmark, '    NNJoltState->FramesWithoutNNStep = Steps ? 0 : NNJoltState->FramesWithoutNNStep + 1;', '''    const uint64 PreparedSamples = Stats.PreparedPhysicalSamples - Previous.PreparedPhysicalSamples;
    const uint64 PreparedBatches = Stats.PreparedPhysicalBatches - Previous.PreparedPhysicalBatches;
    const bool bPreparedFeedback = NNJoltState->PhysicalFeedbackMode != 0;
    if (PreparedSamples != (bPreparedFeedback ? PhysicalSamples : 0)
        || PreparedBatches != (bPreparedFeedback ? Steps : 0))
    { Error = TEXT("Prepared feedback failed its exact per-NN-step joined batch/item accounting."); return false; }
    NNJoltState->FramesWithoutNNStep = Steps ? 0 : NNJoltState->FramesWithoutNNStep + 1;''')
benchmark = once(benchmark, '    Summary->SetNumberField(TEXT("completed_nn_steps"), double(NNSteps));', '''    Summary->SetNumberField(TEXT("completed_nn_steps"), double(NNSteps));
    Summary->SetNumberField(TEXT("physical_feedback_mode"), End.PhysicalFeedbackExecutionMode);
    Summary->SetNumberField(TEXT("prepared_physical_samples"), double(End.PreparedPhysicalSamples - Start.PreparedPhysicalSamples));
    Summary->SetNumberField(TEXT("prepared_physical_batches"), double(End.PreparedPhysicalBatches - Start.PreparedPhysicalBatches));
    Summary->SetStringField(TEXT("physical_feedback_scope"), TEXT("Mode0 retains immediate serial sampling/math; modes1/2 use identical GT samples and resolved inputs with prepared serial/parallel math. Preparation and joined math wall scopes remain inside manager/world timing. Counts describe completed items and joins, not worker residency. No worker GT-profiler calls, reduced cadence, changed tolerance or NN precision."));''')
save(B, benchmark)

L = 'Tools/NN/RunSterilePhysicsBenchmark.ps1'
launcher = read(L)
launcher = once(launcher, '    [switch]$PauseChaos,', "    [switch]$PauseChaos,\n    [ValidateSet('Original','PreparedSerial','PreparedParallel')][string]$FeedbackMode='Original',")
launcher = once(launcher, "$benchHasJoltWorkers = $PSBoundParameters.ContainsKey('JoltWorkerThreads')", "if ($FeedbackMode -ne 'Original' -and $Methods -ne 'NNJoltCrowd') { throw 'Prepared feedback requires the explicit NNJoltCrowd fixture.' }\n$benchHasJoltWorkers = $PSBoundParameters.ContainsKey('JoltWorkerThreads')")
launcher = once(launcher, "if ($PauseChaos) { $benchArgs+=' -PhysicsBenchPauseChaos' }", "if ($PauseChaos) { $benchArgs+=' -PhysicsBenchPauseChaos' }\nif ($Methods -eq 'NNJoltCrowd') { $benchArgs+=' -PhysicsBenchFeedbackMode=' + $FeedbackMode }")
save(L, launcher)

G = 'Tools/Jolt/RunGameModuleSimdBenchmark.ps1'
guard = read(G)
guard = once(guard, '    [switch]$PauseChaos,', "    [switch]$PauseChaos,\n    [ValidateSet('Original', 'PreparedSerial', 'PreparedParallel')][string]$FeedbackMode = 'Original',")
guard = once(guard, 'pauseChaos = [bool]$PauseChaos; processPriority', 'pauseChaos = [bool]$PauseChaos; feedbackMode = $FeedbackMode; processPriority')
guard = once(guard, 'PauseChaos = [bool]$PauseChaos; ProcessPriority', 'PauseChaos = [bool]$PauseChaos; FeedbackMode = $FeedbackMode; ProcessPriority')
save(G, guard)

def write_patch():
    patches=[]
    for rel, original_text in FILES.items():
        changed=(DRAFT/rel).read_text()
        patches.extend(difflib.unified_diff(original_text.splitlines(True),changed.splitlines(True),fromfile='a/'+rel,tofile='b/'+rel))
    (DRAFT/'ExistingFiles.patch').write_text(''.join(patches),encoding='utf-8',newline='\n')
    (DRAFT/'BaselineHashes.json').write_text(json.dumps({rel:hashlib.sha256((ROOT/rel).read_bytes()).hexdigest() for rel in FILES},indent=2)+'\n')
write_patch()
print('Draft kernel, native integration, benchmark provenance and launch controls generated.')
