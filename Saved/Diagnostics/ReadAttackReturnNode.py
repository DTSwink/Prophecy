import unreal
function = unreal.find_object(None, '/Script/GameAnimationSample3.ProphecyAttackControlLibrary:SetAttackReturnToRootBalancing')
assert function, 'Attack return selector is not reflected in the running editor'
print('Available node:', function.get_path_name())
