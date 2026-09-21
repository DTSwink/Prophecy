import unreal
for name in ('CollisionResponse','CollisionResponseType','ECollisionResponse'):
    value=getattr(unreal,name,None)
    print(name,value,dir(value) if value else '')
