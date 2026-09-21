import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user PIE'
fn=unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyPhysicalProfileLibrary:PrintPhysicalBoneProfiles')
assert fn, 'New print function not reflected'
actors=unreal.GameplayStatics.get_all_actors_of_class(ed.get_editor_world(),unreal.ProphecyAgent)
assert actors
agent=next((a for a in actors if a.get_actor_label()=='BP_ProphecyManualPoseAgent'),actors[0])
cdo=unreal.get_default_object(unreal.ProphecyPhysicalProfileLibrary)
text=cdo.call_method('PrintPhysicalBoneProfiles',args=(agent,0.0,unreal.LinearColor(1,1,1,1)))
lines=text.splitlines()
assert lines and lines[0].startswith('head : '), lines[:3]
assert lines[-1].startswith(('foot_','ball_')), lines[-3:]
assert len(lines)==len(set(x.split(' : ')[0] for x in lines))
assert all(' / ' in x for x in lines)
print('Print Physical Bone Profiles: reflected, callable; %d unique PHAT rows; head first, feet last.'%len(lines))
print('First:',lines[0]);print('Last:',lines[-1])
assert cdo.call_method('PrintPhysicalBoneProfiles',args=(None,0.0,unreal.LinearColor(1,1,1,1)))==''
