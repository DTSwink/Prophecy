import unreal
for package in ('/Script/GameAnimationSample3','/Engine/Transient'):
    path=package+'.LIVECODING_ProphecyAgent_0'
    obj=unreal.find_object(None,path)
    print(path, obj)
print([x for x in dir(unreal) if 'ObjectIterator' in x])
