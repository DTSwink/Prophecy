import pathlib,unreal,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
world=ed.get_editor_world()
saved=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
def agents():
    cls=unreal.load_class(None,'/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent_C')
    return {a.get_actor_label():{'transform':str(a.get_actor_transform()),'possession':str(a.get_editor_property('auto_possess_player'))}
            for a in unreal.GameplayStatics.get_all_actors_of_class(world,cls)}
before=agents()
assert len(before)==3, before
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.RepairLibraryDefaults')
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.RefreshUpperInertiaSpace')
def read(name):
    data=(saved/name).read_bytes()
    return data.decode('utf-16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')
report=read('UpperInertiaControlsPins.txt')
assert 'preserved=1' in report and 'defaults=1' in report and ('status=3' in report or 'status=5' in report),report
after=agents()
assert before==after,(before,after)
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Sword.AuditCollisionGraph')
graph=read('SwordThigh/BlueprintGraph.txt')
assert 'ArmsAlpha=-1.000000' in graph, 'Expected new inheriting arm alpha'
(saved/'UpperArmsAlpha-20261002/verified.json').write_text(json.dumps({'blueprint':report,'agents_preserved':after},indent=2))
print('ARMS_ALPHA_READY',report,'THREE_AGENTS_PRESERVED')
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.NN.UpperBodyInertia')
