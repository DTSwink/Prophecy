import unreal,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print(json.dumps(dict(pie=bool(ed.get_game_world()),has_agent_state=hasattr(unreal.ProphecyNNDefenseLibrary,'get_agent_state'),states=[x for x in dir(getattr(unreal,'ProphecyAgentState',object)) if x.isupper()])))
