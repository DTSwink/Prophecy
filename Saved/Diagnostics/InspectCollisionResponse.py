import unreal
print('COLLISION',list(unreal.CollisionResponse))
print('COLLISION_MEMBERS',[x for x in dir(unreal.CollisionResponse) if not x.startswith('_')])
