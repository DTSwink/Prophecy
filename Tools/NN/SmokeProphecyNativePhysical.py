"""Run once on initialized native PIE fixture after Live Coding."""
import unreal,json
from pathlib import Path
w=unreal.EditorLevelLibrary.get_game_world()
a=next(x for x in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if x.get_name()=='NativePhysicalTest')
m=a.get_agent_mesh();lib=unreal.ConstraintInstanceBlueprintLibrary
assert a.call_method('GetNativeBodySample',args=('pelvis',)) is not None
assert len(a.get_components_by_class(unreal.SkeletalMeshComponent))==1
assert 'ProphecyNNLocomotionAnimInstance' in m.get_anim_instance().get_class().get_name()
assert not a.get_editor_property('bNativeUseAuthoredAngularLimits')
constraints=m.get_constraints(False)
original_linear=[lib.get_linear_limits(c)[1:] for c in constraints]
def angular_free():
    return all(all(v==unreal.AngularConstraintMotion.ACM_FREE for v in lib.get_angular_limits(c)[1::2]) for c in constraints)
assert angular_free()
assert a.call_method('SetNativeUseAuthoredAngularLimits',args=(True,))
assert not angular_free()
assert a.call_method('SetNativeUseAuthoredAngularLimits',args=(False,))
assert angular_free()
assert original_linear==[lib.get_linear_limits(c)[1:] for c in constraints]
assert not a.call_method('SetNativeBodyStrength',args=('not_a_bone',1.,1.))
assert not a.call_method('SetNativeBodyStrength',args=('hand_r',-1.,1.))
assert a.call_method('SetNativeBodyStrengthBelow',args=('upperarm_r',.5,.5,True))==3
assert a.call_method('SetNativeBodyStrength',args=('hand_r',0.,0.))
assert a.call_method('SetNativePhysicalSimulation',args=(False,))
assert not m.is_simulating_physics('pelvis')
assert a.call_method('GetNativeBodySample',args=('pelvis',)) is None
assert m.get_anim_instance() is not None
assert a.call_method('SetNativePhysicalSimulation',args=(True,))
assert m.is_simulating_physics('pelvis')
assert m.get_anim_instance() is not None
# This must safely return false, not enter native GetBodyTargetTransform before
# deferred target actors have been created by PhysicalAnimation's next tick.
assert a.call_method('GetNativeBodySample',args=('pelvis',)) is None
assert a.call_method('SetNativeBodyStrengthBelow',args=('upperarm_r',1.,1.,True))==3
path=Path(unreal.Paths.project_saved_dir()).resolve()/'NativePhysical/smoke.json'
path.write_text(json.dumps({'passed':True,'skeletal_mesh_count':1,'constraints':len(constraints),
    'mode_toggle':True,'deferred_target_guard':True,'angular_limits_toggle':True,'linear_anchors_unchanged':True,
    'invalid_bone_and_negative_strength_rejected':True},indent=2))
print('Native final smoke passed',path)
