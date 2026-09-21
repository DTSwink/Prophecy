import unreal
cls=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyNNDefenseLibrary')
cdo=unreal.get_default_object(cls)
print('CLASS',cls,'CDO',cdo)
try: print('STATE',cdo.call_method('GetAgentState',(None,)))
except Exception as e:print('ERROR',e)
print('HAS',hasattr(unreal,'ProphecyAgentState'))
