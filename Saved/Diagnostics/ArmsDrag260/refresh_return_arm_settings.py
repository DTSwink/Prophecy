import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user PIE'
w=ed.get_editor_world();p=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics')
graph=p/'SwordThigh/BlueprintGraph.txt'
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
before=graph.read_bytes().decode('utf-16' if graph.read_bytes().startswith(b'\xff\xfe') else 'utf-8-sig');(p/'ArmsDrag260/return_arm_pins_before.txt').write_text(before,encoding='utf-8')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RefreshArmReturnSettings')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
after=graph.read_bytes().decode('utf-16' if graph.read_bytes().startswith(b'\xff\xfe') else 'utf-8-sig');(p/'ArmsDrag260/return_arm_pins_after.txt').write_text(after,encoding='utf-8')
def nodes(text):
 return {b.splitlines()[0]:b.splitlines()[1:] for b in text.split('\n\n') if b and '| Set Attack Arm Return To Neutral' in b.splitlines()[0]}
old,new=nodes(before),nodes(after)
checks=[]
for key,lines in old.items():
 current=new.get(key,[])
 preserved=all(line in current for line in lines if not line.strip().startswith('self='))
 defaults={n:next((x.strip().split('=',1)[1].split()[0] for x in current if x.strip().startswith(n+'=')),None) for n in ['LeftHoldDurationSeconds','LeftBlendToNNDurationSeconds','LeftAlpha','RightAlpha']}
 checks.append(dict(node=key,preserved=preserved,defaults=defaults))
report={'nodes':checks,'asset_saved':False}
(p/'ArmsDrag260/return_arm_pin_verification.json').write_text(json.dumps(report,indent=2))
print('RETURN_ARM_PINS',report)
assert checks and all(x['preserved'] and all(float(v)==(-1 if 'Seconds' in k else 1) for k,v in x['defaults'].items()) for x in checks)

