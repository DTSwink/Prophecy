"""Generate a source-only patch. Writes exclusively beside this script."""
from pathlib import Path
import hashlib
import json
from collections import Counter

draft = Path(__file__).resolve().parent
root = draft.parents[2]
relative = 'Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp'
source = (root / relative).read_text(encoding='utf-8-sig')
result = source
patch = ['*** Begin Patch', '*** Update File: ' + relative]

def change(old, new):
    global result
    assert result.count(old) == 1, old[:120]
    result = result.replace(old, new)
    patch.append('@@')
    patch.extend('-' + line for line in old.splitlines())
    patch.extend('+' + line for line in new.splitlines())

cache = '''	class FSampledTrainingRotations
	{
	public:
		explicit FSampledTrainingRotations(TConstArrayView<FTransform> InTransforms)
			: Transforms(InTransforms)
		{
			static_assert(FullBodyBoneCount <= 32);
			check(Transforms.Num() == FullBodyBoneCount);
		}

		const FMat3f& Get(int32 Index)
		{
			check(Transforms.IsValidIndex(Index));
			const uint32 Bit = uint32(1) << Index;
			if ((ReadyMask & Bit) == 0)
			{
				Matrices[Index] = MirrorYBasis(QuatToMatrix(Transforms[Index].GetRotation()));
				ReadyMask |= Bit;
			}
			return Matrices[Index];
		}

#if WITH_DEV_AUTOMATION_TESTS
		uint32 CachedMaskForTests() const { return ReadyMask; }
#endif

	private:
		TConstArrayView<FTransform> Transforms;
		FMat3f Matrices[FullBodyBoneCount];
		uint32 ReadyMask = 0;
	};

'''
change('\tFVector ApplyLinearFeedbackTolerance(', cache + '\tFVector ApplyLinearFeedbackTolerance(')

start = source.index('bool AProphecyNNLocomotionManager::ResamplePhysicalAgentState(')
resample = source[start:source.index('\nvoid AProphecyNNLocomotionManager::BuildInputBatch(', start)]
lower_start = resample.index('\tconst FTransform& Pelvis = ActualTransforms[0];')
lower_end = resample.index('\tCleanState(Sample, *Impl);') + len('\tCleanState(Sample, *Impl);')
lower = resample[lower_start:lower_end]
upper_start = resample.index('\tFMemory::Memzero(UpperSample, UpperStateDim * sizeof(float));')
upper_end = resample.index('\tCleanUpperState(UpperSample);') + len('\tCleanUpperState(UpperSample);')
upper = resample[upper_start:upper_end]

def cached(block):
    block = block.replace('\tFImpl::FAgent& Agent = Impl->Agents[AgentIndex];\n', '')
    block = block.replace('Impl->', 'Impl.').replace('*Impl', 'Impl')
    swaps = {
        'MirrorYBasis(QuatToMatrix(Pelvis.GetRotation()))': 'TrainingRotations.Get(0)',
        'MirrorYBasis(QuatToMatrix(ActualTransforms[RuntimeLimb.Start].GetRotation()))': 'TrainingRotations.Get(RuntimeLimb.Start)',
        'MirrorYBasis(QuatToMatrix(ActualTransforms[RuntimeLimb.End].GetRotation()))': 'TrainingRotations.Get(RuntimeLimb.End)',
        'MirrorYBasis(QuatToMatrix(ActualTransforms[RuntimeLimb.Toe].GetRotation()))': 'TrainingRotations.Get(RuntimeLimb.Toe)',
        'MirrorYBasis(\n\t\t\tQuatToMatrix(ActualTransforms[BodyIndex].GetRotation()))': 'TrainingRotations.Get(BodyIndex)',
        'MirrorYBasis(\n\t\t\tQuatToMatrix(ActualTransforms[ParentIndex].GetRotation()))': 'TrainingRotations.Get(ParentIndex)',
        'MirrorYBasis(QuatToMatrix(ActualTransforms[Arm.End].GetRotation()))': 'TrainingRotations.Get(Arm.End)',
        'MirrorYBasis(QuatToMatrix(ActualTransforms[Arm.Start].GetRotation()))': 'TrainingRotations.Get(Arm.Start)',
    }
    for old, new in swaps.items():
        block = block.replace(old, new)
    assert 'QuatToMatrix' not in block
    return '\n'.join('\t' + line if line else '' for line in block.splitlines())

helpers = '''	// These raw encoders stay at their original positions around the unchanged tolerance stages.
	void EncodePhysicalLowerSample(const AProphecyNNLocomotionManager::FImpl& Impl,
		const AProphecyNNLocomotionManager::FImpl::FAgent& Agent,
		TConstArrayView<FTransform> ActualTransforms, FSampledTrainingRotations& TrainingRotations, float* Sample)
	{
		using FImpl = AProphecyNNLocomotionManager::FImpl;
''' + cached(lower) + '''
	}

	void EncodePhysicalUpperSample(const AProphecyNNLocomotionManager::FImpl& Impl,
		TConstArrayView<FTransform> ActualTransforms, FSampledTrainingRotations& TrainingRotations, float* UpperSample)
	{
		using FImpl = AProphecyNNLocomotionManager::FImpl;
''' + cached(upper) + '''
	}

#if WITH_DEV_AUTOMATION_TESTS
#include "Tests/ProphecyNNPhysicalRotationCacheTests.inl"
#endif

'''
change('\tvoid BlendStateVector(float* State, const float* Target, int32 Offset, float Weight)',
       helpers + '\tvoid BlendStateVector(float* State, const float* Target, int32 Offset, float Weight)')
change(lower, '''	FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
	// Cache only this successful sample; no pose, tolerance, or recurrent state survives here.
	FSampledTrainingRotations TrainingRotations(ActualTransforms);
	EncodePhysicalLowerSample(*Impl, Agent, ActualTransforms, TrainingRotations, Sample);''')
change(upper, '\tEncodePhysicalUpperSample(*Impl, ActualTransforms, TrainingRotations, UpperSample);')

def section(text, first, last):
    return text[text.index(first):text.index(last, text.index(first))]

oracle_start = '\tvoid EncodeComponentPoseToNNStates('
oracle_end = '\n\t// These raw encoders'  # inserted immediately after the unchanged oracle
old_oracle = section(source, oracle_start, '\n\tvoid BlendStateVector(')
new_oracle = section(result, oracle_start, oracle_end)
assert old_oracle == new_oracle
new_resample = section(result, 'bool AProphecyNNLocomotionManager::ResamplePhysicalAgentState(',
                       '\nvoid AProphecyNNLocomotionManager::BuildInputBatch(')
lower_tail_start = '\tfloat* Previous = StateSlice(Impl->PrevStateBuffer, AgentIndex);'
lower_tail_end = '\tFMemory::Memzero(UpperSample, UpperStateDim * sizeof(float));'
old_lower_tail = section(resample, lower_tail_start, lower_tail_end)
new_lower_tail = section(new_resample, lower_tail_start, '\tEncodePhysicalUpperSample(')
assert old_lower_tail == new_lower_tail
upper_tail_start = '\tauto ApplyUpperLinearTolerance ='
assert resample[resample.index(upper_tail_start):] == new_resample[new_resample.index(upper_tail_start):]

test_relative = 'Source/GameAnimationSample3/Private/Tests/ProphecyNNPhysicalRotationCacheTests.inl'
assert not (root / test_relative).exists()
tests = (draft / 'ProphecyNNPhysicalRotationCacheTests.inl').read_text(encoding='utf-8')
patch.append('*** Add File: ' + test_relative)
patch.extend('+' + line for line in tests.splitlines())
launcher_relative = 'Tools/Jolt/RunFoundationTests.ps1'
launcher = (root / launcher_relative).read_text(encoding='utf-8-sig')
old_filter = 'NN\\.PhysicalTargets|Fists\\.Cache'
new_filter = 'NN\\.PhysicalTargets|NN\\.PhysicalFeedback(?:Tolerance)?|Fists\\.Cache'
assert launcher.count(old_filter) == 1
line = next(line for line in launcher.splitlines() if old_filter in line)
patch.extend(['*** Update File: ' + launcher_relative, '@@', '-' + line, '+' + line.replace(old_filter, new_filter)])
patch.append('*** End Patch')
(draft / 'PhysicalRotationCache.apply-patch.txt').write_text('\n'.join(patch) + '\n', encoding='utf-8')
verification = {
    'active_manager_sha256': hashlib.sha256((root / relative).read_bytes()).hexdigest(),
    'active_runner_sha256': hashlib.sha256((root / launcher_relative).read_bytes()).hexdigest(),
    'unchanged_existing_encoder': True,
    'unchanged_lower_tolerance_and_upper_pointer_setup': True,
    'unchanged_upper_tolerance_and_entire_recurrent_tail': True,
    'source_only_not_compiled_or_executed': True,
}
contracts = {}
for name in ['prophecy_lower_body_runtime.json', 'prophecy_lower_body_walk_runtime.json', 'prophecy_upper_body_runtime.json']:
    path = root / 'Content/locomotion/NN' / name
    contracts[name] = json.loads(path.read_text(encoding='utf-8-sig'))
upper_contract = contracts['prophecy_upper_body_runtime.json']
names = upper_contract['body_names']
parents = upper_contract['parents_body']
counts = {}
for policy, name in [('run', 'prophecy_lower_body_runtime.json'), ('walk', 'prophecy_lower_body_walk_runtime.json')]:
    contract = contracts[name]
    assert names == contract['body_names'] and parents == contract['parents_body']
    requests = [0]
    for limb in contract['ik_limb_specs']:
        requests.extend(limb[key] for key in ['start', 'end', 'toe'])
    for bone in upper_contract['core_bones']:
        index = names.index(bone)
        requests.extend([index, parents[index]])
    for arm in upper_contract['arm_specs']:
        requests.extend([arm['end'], arm['start']])
    frequencies = Counter(requests)
    counts[policy] = {
        'sampled_rotations_before': len(requests), 'sampled_rotations_after': len(frequencies),
        'saved_conversions': len(requests) - len(frequencies),
        'repeated_bones': {names[index]: count for index, count in frequencies.items() if count > 1},
        'unused_sampled_rotation_bones': [bone for index, bone in enumerate(names) if index not in frequencies],
    }
verification['sampled_rotation_counts'] = counts
verification['contract_sha256'] = {
    name: hashlib.sha256((root / 'Content/locomotion/NN' / name).read_bytes()).hexdigest() for name in contracts
}
(draft / 'SourceVerification.json').write_text(json.dumps(verification, indent=2) + '\n', encoding='utf-8')
print(json.dumps(verification, indent=2))
