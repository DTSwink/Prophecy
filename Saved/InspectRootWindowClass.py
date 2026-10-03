import unreal
c=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyNNRootWindowLibrary')
print('CLASS',c)
if c:
 o=unreal.get_default_object(c)
 print('CDO',o,'METHODS',[x for x in dir(o) if 'root_window' in x])
