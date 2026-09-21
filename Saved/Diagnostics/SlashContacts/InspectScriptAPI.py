import unreal,json
print(json.dumps([s for s in dir(unreal.SystemLibrary) if 'latent' in s or 'timer' in s]))
