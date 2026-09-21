import unreal,pathlib,shutil,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
w=ed.get_editor_world()
assert w.get_name()=='testNN',w.get_name()
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CombatDemo'
folder.mkdir(parents=True,exist_ok=True)
source=pathlib.Path(unreal.Paths.project_content_dir())/'testNN.umap'
backup=folder/'testNN_before.umap'
if not backup.exists():shutil.copy2(source,backup)
actors={a.get_actor_label():a for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent)}
a=actors['BP_ProphecyManualPoseAgent'];d=actors['BP_ProphecyManualPoseAgent4']
assert a.get_editor_property('auto_possess_player')==unreal.AutoReceiveInput.PLAYER0
rows=[]
for actor,opponent in [(a,d),(d,a)]:
 p=actor.get_actor_location()
 rows.append(dict(label=actor.get_actor_label(),location=[p.x,p.y,p.z],rotation=str(actor.get_actor_rotation())))
 actor.modify()
 actor.set_editor_property('CombatDemoOpponent',opponent)
 actor.set_editor_property('CombatDemoUseDodge',True)
 actor.set_editor_property('CombatDemoAttackEveryFrames',60)
 actor.set_editor_property('CombatDemoEnabled',True)
(folder/'setup.json').write_text(json.dumps(rows,indent=2))
assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
print('COMBAT_DEMO_CONFIGURED',rows)
