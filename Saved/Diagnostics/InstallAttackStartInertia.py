from pathlib import Path
p=Path('Source/GameAnimationSample3/Private')
def edit(name, old, new, n=1):
 f=p/name;s=f.read_text(encoding='utf-8');assert old in s,(name,old[:80]);s=s.replace(old,new,n);f.write_text(s,encoding='utf-8')
for name in ['ProphecyNNLocomotionManager.cpp','ProphecyAgent.cpp','ProphecyNNLocomotionAnimInstance.cpp','ProphecyAgentResetPhysics.cpp']:
 f=p/name;s=f.read_text(encoding='utf-8');s='#include "ProphecyAttackStartInertia.h"\n'+s;f.write_text(s,encoding='utf-8')
edit('ProphecyNNLocomotionManager.cpp','ProphecyUpperBodyInertia::Remove(AgentActor);','ProphecyUpperBodyInertia::Remove(AgentActor);\n\t\tProphecyAttackStartInertia::Remove(AgentActor);')
edit('ProphecyNNLocomotionManager.cpp','\t\t\tPublishAgentPose(AgentIndex, Agent.PublishedPoseTimeSeconds);\n\t\t}\n\t}\n}\n', '\t\t\tPublishAgentPose(AgentIndex, Agent.PublishedPoseTimeSeconds);\n\t\t}\n\t\tProphecyAttackStartInertia::Update(AgentActors[AgentIndex],PoseStoreAgentBase+AgentIndex);\n\t}\n}\n')
edit('ProphecyNNSlashRuntime.inl','\tSlash.bActive = true;\n', '''\tif (!bHalf) ProphecyAttackStartInertia::Begin(Actor,PoseStoreAgentBase+Handle.Index,
        TransformSlice(Impl->PreviousComponentTransformBuffer,Handle.Index)[0]
            *SlashComponentWorld(Actor,Agent.PreviousPublishedRoot,Agent.PreviousPublishedYaw),Current[0]*StartCarrier);
\tSlash.bActive = true;
''')
edit('ProphecyNNSlashRuntime.inl','\tif (bHalf)\n\t{\n\t\t// A running full attack', '\tif (bHalf)\n\t{\n\t\tProphecyAttackStartInertia::Cancel(Actor);\n\t\t// A running full attack')
edit('ProphecyNNSlashRuntime.inl','\tProphecyAttackTrim::CancelHalfFrame(Actor);', '\tProphecyAttackStartInertia::Cancel(Actor);\n\tProphecyAttackTrim::CancelHalfFrame(Actor);')
# Shared physical + manual kinematic targets, both source variants.
edit('ProphecyAgent.cpp','\t\tFProphecyNNPoseStore::ApplyRigidCalves(PoseAgentId, Pose, BoneNames, InterpolatedWorldTransforms);','\t\tFProphecyNNPoseStore::ApplyRigidCalves(PoseAgentId, Pose, BoneNames, InterpolatedWorldTransforms);\n\t\tProphecyAttackStartInertia::Apply(PoseAgentId,BoneNames,InterpolatedWorldTransforms);')
edit('ProphecyAgent.cpp','\tFProphecyNNPoseStore::ApplyRigidCalves(PoseAgentId, Pose, BoneNames, InterpolatedWorldTransforms);\n\treturn true;', '\tFProphecyNNPoseStore::ApplyRigidCalves(PoseAgentId, Pose, BoneNames, InterpolatedWorldTransforms);\n\tProphecyAttackStartInertia::Apply(PoseAgentId,BoneNames,InterpolatedWorldTransforms);\n\treturn true;')
# Single-bone debug/sword reads must use identical fully connected corrected pose.
edit('ProphecyAgent.cpp','\tconst int32 PoseIndex = Pose.BoneNames.IndexOfByKey(BoneName);', '''\tif (ProphecyAttackStartInertia::Active(PoseAgentId))
    {
        TArray<FName> Names;TArray<FTransform> Future,Visible;
        if (ReadNNFutureWorldPose(Names,Future,Visible,InterpolationAlpha))
        {
            const int32 I=Names.IndexOfByKey(BoneName);
            if(Visible.IsValidIndex(I))
            {
                InterpolatedWorldTransform=Visible[I];CurrentWorldTransform=Future[I];
                const int32 Source=Pose.BoneNames.IndexOfByKey(BoneName);
                PreviousWorldTransform=Pose.PreviousComponentTransforms.IsValidIndex(Source)
                    ? Pose.PreviousComponentTransforms[Source]*Pose.PreviousComponentWorldTransform:Visible[I];
                return true;
            }
        }
    }
\tconst int32 PoseIndex = Pose.BoneNames.IndexOfByKey(BoneName);''')
edit('ProphecyNNLocomotionAnimInstance.cpp','\t\tconst bool bRecoveringCalfLength=', '''\t\tif (bApplyPelvis && bApplyLegs && bApplyUpperBody)
            ProphecyAttackStartInertia::Apply(AgentId,CurrentPose.BoneNames,DesiredComponentTransforms,EvaluationComponentWorldTransform);
\t\tconst bool bRecoveringCalfLength=''')
for meth in ['ForgetReset','CaptureReset','RestoreReset','Cancel']:
 edit('ProphecyAgentResetPhysics.cpp',f'ProphecyUpperBodyInertia::{meth}(Agent);',f'ProphecyUpperBodyInertia::{meth}(Agent);\n    ProphecyAttackStartInertia::{meth}(Agent);')
edit('ProphecyAgent.cpp','ProphecyPelvisInertia::Remove(this);','ProphecyPelvisInertia::Remove(this);\n    ProphecyAttackStartInertia::Remove(this);')
print('Hooks installed')
