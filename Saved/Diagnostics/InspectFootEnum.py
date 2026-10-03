import unreal
e=unreal.load_object(None,'/Script/GameAnimationSample3.EProphecyAttackFootLocomotionMode')
t=unreal.get_type_from_enum(e)
print(e,t,dir(t))
print([n for n in dir(unreal) if 'FootLocomotion' in n])
