import pathlib,re
root=pathlib.Path(__file__).resolve().parents[3]
def edit(path,fn):
 p=root/path;s=p.read_text();v=fn(s);assert v!=s,path;p.write_text(v)
def sub(s,pattern,repl,n=1):
 out,count=re.subn(pattern,repl,s,flags=re.S);assert count==n,(pattern,count,n);return out
def cut_function(s,name):
 start=s.index('bool AProphecyAgent::'+name+'(');end=s.index('\n}\n',start)+3
 return s[:start]+s[end:]
def agent_h(s):
 s=sub(s,r'\t/\*\* Full and half attacks: allowed hand distance.*?float AttackHandClampLeewayCm = 0;\n','')
 s=sub(s,r'\t/\*\* Locomotion hands: maximum elbow-to-hand.*?float LocomotionForearmClampLeewayCm = 0;\n','')
 return s.replace(', bOverrideLocomotionHandClamp = false','').replace(', bLocomotionHandClamp = false','').replace(', LocomotionHandClampLeewayCm = 0','')
edit('Source/GameAnimationSample3/Public/ProphecyAgent.h',agent_h)
edit('Source/GameAnimationSample3/Private/ProphecyAgent.cpp',lambda s:cut_function(cut_function(cut_function(s,'SetAttackHandClamp'),'SetLocomotionHandClamp'),'SetLocomotionForearmClamp'))
edit('Source/GameAnimationSample3/Public/ProphecyNNLocomotionManager.h',lambda s:sub(s,r'\t/\*\* Limit each locomotion hand.*?float HandClampLengthMultiplier = 1.0f;\n',''))
edit('Source/GameAnimationSample3/Public/ProphecyNNDefenseLibrary.h',lambda s:sub(s,r'    UFUNCTION\([^\n]*\)\n    static bool Set(?:Parry|Dodge)(?:Hand|Forearm)Clamp[^\n]*\n','',4))
edit('Source/GameAnimationSample3/Private/ProphecyNNDefenseLibrary.cpp',lambda s:sub(s,r'DEFENSE_CLAMP\((?:Parry|Dodge),[^\n]*,(?:Hand|Forearm)\)\n','',4))
edit('Source/GameAnimationSample3/Private/ProphecyDefenseControls.h',lambda s:s.replace('Foot, Calf, Hand, Forearm','Foot, Calf').replace('Foot,Calf,Hand,Forearm','Foot,Calf'))
edit('Source/GameAnimationSample3/Private/ProphecyDefenseControls.cpp',lambda s:s.replace('Limb==ELimb::Foot?Mode.Foot:Limb==ELimb::Calf?Mode.Calf:Limb==ELimb::Hand?Mode.Hand:Mode.Forearm','Limb==ELimb::Foot?Mode.Foot:Mode.Calf'))
edit('Source/GameAnimationSample3/Public/ProphecyClampProfileLibrary.h',lambda s:s.replace('Calf, Forearm, Hand, Foot','Calf=0, Foot=3').replace('all existing clamp types','both leg clamp types'))
edit('Source/GameAnimationSample3/Private/ProphecyClampEase.h',lambda s:s.replace('Foot, Calf, Hand, Forearm, PhysicalCalf','Foot, Calf, PhysicalCalf'))

def manager(s):
 s=s.replace('\t\t\tFProphecyNNAttackHandClamp HandClamp;\n','')
 s=s.replace('bool bClampFoot = false, bClampCalf = false, bClampHand = false;','bool bClampFoot = false, bClampCalf = false;')
 s=s.replace('\t\tbool bClampForearm = false;\n\t\tfloat ForearmLeeway = 0;\n','')
 s=s.replace(', HandClampLengthMultiplier = 1','').replace(', HandLeeway = 0','')
 s=sub(s,r'\t\t\t\tconst float Distance = LowerAxis.Size\(\);.*?\t\t\t\tPositions\[Arm.End\] = End;', '''\t\t\t\t// Forearms have one anatomical length in every locomotion mode.
\t\t\t\tLowerAxis = SafeNormal(LowerAxis, SafeNormal(TransformRow(Impl->UpperLocalOffsets[Arm.End], Rotations[Arm.Start]))) * Arm.Lengths.Y;
\t\t\t\tEnd = Positions[Arm.Mid] + LowerAxis;
\t\t\t\tPositions[Arm.End] = End;''')
 s=sub(s,r'\tC.bClampHand =.*?\tC.ForearmLeeway =[^\n]*\n','')
 s=sub(s,r'\tif\(ClampAttack\)\{Effective.bClampHand[^\n]*\n','')
 s=sub(s,r'\t\tEffective.bClampHand=D[^\n]*\n\t\tEffective.bClampForearm=D[^\n]*\n','')
 s=s.replace('Effective.HandLeeway=D->Hand.LeewayCm*.01f;Effective.ForearmLeeway=D->Forearm.LeewayCm*.01f;','')
 s=sub(s,r'\t\t\t\telse\n\t\t\t\t\{\n\t\t\t\t\tconst auto& L=Impl->UpperArms\[S\];.*?\n\t\t\t\t\}','')
 s=sub(s,r'\tEffective.HandLeeway=Ease[^\n]*\n\tEffective.ForearmLeeway=Ease[^\n]*\n','')
 s=sub(s,r'\tif\(!ClampDefense && !ClampAttack\)\{C.HandLeeway[^\n]*\n','')
 s=sub(s,r'\tFProphecyNNAttackHandClamp PresentationHandClamp=.*?\n\tif \(bDefensePose\)','\tif (bDefensePose)')
 s=sub(s,r'\t\t\tD.Hand.LeewayCm=[^\n]*\n','')
 s=sub(s,r'\t\t\tconst bool Hand=D.Hand[^\n]*\n','')
 s=s.replace('(Foot || Calf || Hand || Forearm)','(Foot || Calf)')
 s=sub(s,r'\t\t\t\t\tif \(Hand \|\| Forearm\) for \(const auto& Arm:Impl->UpperArms\).*?\n\t\t\t\t\t\}\n','')
 s=s.replace('''\t\t// Arm inertia already solved reach and transitions outgoing lengths into
\t\t// the configured clamp range. Re-clamping publication would undo continuity.
\t\tPresentationHandClamp.bEnabled=false;''','\t\t// Arm inertia publishes the same fixed geometry as the normal decoder.')
 s=sub(s,r'\tFProphecyNNForearmClamp ForearmClamp;.*?\n\tFProphecyNNPoseStore::SetAgentLocalPose\(','''\tFProphecyNNFixedArms FixedArms;
\tfor(int32 Side=0;Side<2;++Side)
\t{
\t\tconst auto& Arm=Impl->UpperArms[Side];
\t\tFixedArms.ForearmOffsets[Side]=LocalTrainingToUnreal(Impl->UpperLocalOffsets[Arm.End])*100.;
\t\tfor(auto Pose:{PreviousComponentTransforms,ComponentTransforms})
\t\t\tPose[Arm.End].SetLocation(Pose[Arm.Mid].TransformPosition(FixedArms.ForearmOffsets[Side]));
\t\tLocalTransforms[Arm.End]=ComponentTransforms[Arm.End].GetRelativeTransform(ComponentTransforms[Arm.Mid]);
\t}
\tFProphecyNNPoseStore::SetAgentLocalPose(''')
 s=s.replace('PresentationHandClamp, ForearmClamp,Agent.Slash.bActive && Agent.Slash.bHalf','FixedArms,Agent.Slash.bActive && Agent.Slash.bHalf')
 return s
edit('Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp',manager)

def pose_h(s):
 s=sub(s,r'struct FProphecyNNAttackHandClamp.*?(?=struct GAMEANIMATIONSAMPLE3_API FProphecyNNPoseSnapshot)', '''// Anatomical wrist offsets, shared by every policy and interpolated presentation.
struct FProphecyNNFixedArms
{
\tFVector ForearmOffsets[2] = {FVector::ZeroVector, FVector::ZeroVector};
};

''')
 s=s.replace('FProphecyNNAttackHandClamp AttackHandClamp;\n\tFProphecyNNForearmClamp ForearmClamp;','FProphecyNNFixedArms FixedArms;')
 s=s.replace('AttackHandClamp = FProphecyNNAttackHandClamp();\n\t\tForearmClamp = FProphecyNNForearmClamp();','FixedArms = FProphecyNNFixedArms();')
 s=sub(s,r'\t\tconst FProphecyNNAttackHandClamp& HandClamp =.*?bool bHalfAttack = false\);','\t\tconst FProphecyNNFixedArms& FixedArms = FProphecyNNFixedArms(),bool bHalfAttack = false);')
 s=s.replace('bool bRigidForearms = false','bool bSpecialPresentation = false').replace('Attack presentation: keep fixed hand-parent offsets after world interpolation.','Every mode: keep anatomical hand-parent offsets after world interpolation.')
 return s
edit('Source/GameAnimationSample3/Public/ProphecyNNPoseTypes.h',pose_h)
def pose_cpp(s):
 s=s.replace('GProphecyNNRigidForearms','GProphecyNNSpecialPresentation').replace('bool bRigidForearms,','bool bSpecialPresentation,').replace('if (bRigidForearms)','if (bSpecialPresentation)').replace('if (bRigidForearms &&','if (bSpecialPresentation &&')
 s=s.replace('const FProphecyNNAttackHandClamp& HandClamp, const FProphecyNNForearmClamp& ForearmClamp,bool bHalfAttack','const FProphecyNNFixedArms& FixedArms,bool bHalfAttack')
 s=s.replace('Snapshot.AttackHandClamp = HandClamp;\n\tSnapshot.ForearmClamp = ForearmClamp;','Snapshot.FixedArms = FixedArms;')
 start=s.index('\tif (!Snapshot.ForearmClamp.bEnabled)',s.index('void FProphecyNNPoseStore::ApplyRigidForearms'))
 end=s.index('\n}\n',start)
 s=s[:start]+'''\tstatic const FName Hands[] = { TEXT("hand_l"), TEXT("hand_r") };
\tstatic const FName Forearms[] = { TEXT("lowerarm_l"), TEXT("lowerarm_r") };
\tfor (int32 Side=0;Side<2;++Side)
\t{
\t\tconst int32 H=BoneNames.IndexOfByKey(Hands[Side]),E=BoneNames.IndexOfByKey(Forearms[Side]);
\t\tconst FVector& Offset=Snapshot.FixedArms.ForearmOffsets[Side];
\t\tif(Transforms.IsValidIndex(H) && Transforms.IsValidIndex(E) && !Offset.IsNearlyZero())
\t\t\tTransforms[H].SetTranslation(Transforms[E].TransformPosition(Offset));
\t}'''+s[end:]
 return s
edit('Source/GameAnimationSample3/Private/ProphecyNNPoseTypes.cpp',pose_cpp)
print('Removed arm clamp APIs, decoder ranges and snapshot allowances')
