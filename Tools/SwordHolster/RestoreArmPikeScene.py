"""Restore only the recorded arm-pike sword placement; preserve Blueprint tuning."""
import json, math, pathlib, unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'User Play left untouched'
world=ed.get_editor_world()
assert world.get_path_name()=='/Game/explosionVFX.explosionVFX'
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
reference=json.loads((root/'PikeSlide/restore-reference.json').read_text())
arm=json.loads((root/'PikeSlide/probe.json').read_text())['samples']
previous={s['t']:s for s in json.loads((root/'CleanPike/play.json').read_text())['samples']}
offsets=[[s['sword']['p'][i]-previous[s['t']]['position'][i] for i in range(3)]
         for s in arm if not s['cuts'] and s['t'] in previous and not previous[s['t']]['cuts']]
assert len(offsets)==15
error=max(math.dist(v,offsets[0]) for v in offsets)
assert error<1.e-6,'Recorded trajectories differ; cannot reconstruct exact launch'
base=next(a for a in reference['actors'] if a['name']=='A_Sword_C_1')['actor']
position=[base['p'][i]+offsets[0][i] for i in range(3)]
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
sword=next(a for a in actors if a.get_name()=='A_Sword_C_1')
mannequin=next(a for a in actors if a.get_name()=='SkeletalMeshActor_0')
def tr(t):
    p=t.translation;q=t.rotation;s=t.scale3d
    return {'p':[p.x,p.y,p.z],'q':[q.x,q.y,q.z,q.w],'s':[s.x,s.y,s.z]}
mannequin_reference=next(a for a in reference['actors'] if a['name']=='SkeletalMeshActor_0')['actor']
mannequin_now=tr(mannequin.get_actor_transform())
assert all(math.dist(mannequin_now[k],mannequin_reference[k])<1.e-6 for k in ('p','q','s')),'Mannequin also moved; inspect before restoring'
before=tr(sword.get_actor_transform())
receipt={'before':before,'target':dict(p=position,q=base['q'],s=base['s']),
         'mannequin_unchanged':True,'matching_precontact_samples':len(offsets),
         'max_trajectory_offset_error_cm':error,'blueprints_edited':False,'play_started':False,'saved':False}
path=root/'PikeSlide/restored-scene.json'
path.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
with unreal.ScopedEditorTransaction('Restore recorded arm pike launch position'):
    sword.modify()
    target=unreal.Transform(location=unreal.Vector(*position),rotation=unreal.Quat(*base['q']).rotator(),scale=unreal.Vector(*base['s']))
    sword.set_actor_transform(target,False,True)
after=tr(sword.get_actor_transform())
assert all(math.dist(after[k],receipt['target'][k])<1.e-6 for k in ('p','q','s'))
assert unreal.EditorLoadingAndSavingUtils.save_map(world,'/Game/explosionVFX')
receipt.update(after=after,saved=True)
path.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
