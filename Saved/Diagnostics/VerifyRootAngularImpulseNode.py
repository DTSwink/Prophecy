import unreal
cls=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyRootPhysicsLibrary')
assert cls
lib=unreal.get_default_object(cls)
assert lib.call_method('AddRootAngularImpulse',args=(None,unreal.Vector(0,0,1),True)) is False
print('Add Root Angular Impulse: reflected and callable; null-agent guard passed.')
