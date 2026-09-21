import unreal
print([n for n in dir(unreal.MathLibrary) if 'stream' in n])
print([n for n in dir(unreal.RandomStream) if not n.startswith('_')])
r=unreal.RandomStream(initial_seed=100)
print(r)
