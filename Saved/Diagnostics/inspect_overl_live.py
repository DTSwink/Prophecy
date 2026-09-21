import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world()
print('GAME',w)
print('character methods', [x for x in dir(unreal.ProphecyJoltCharacterComponent) if any(k in x for k in ['body','state','rig','joint'])])
if w:
 for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
  print('AGENT',a.get_name(),'state',unreal.ProphecyNNCombatLibrary.get_agent_state(a) if hasattr(unreal,'ProphecyNNCombatLibrary') else 'unknown')
  print('COMP',[(c.get_name(),c.get_class().get_name()) for c in a.get_components_by_class(unreal.ActorComponent) if 'Jolt' in c.get_class().get_name()])
print('agent access',[x for x in dir(unreal.ProphecyAgent) if any(k in x for k in ['attack','state','jolt','pose'])])
