import unreal
print([n for n in dir(unreal.MaterialEditingLibrary) if any(w in n for w in ['connect_material','disconnect','expression','property_input'])])
print([n for n in dir(unreal) if 'TranslucencyLightingMode' in n])
if hasattr(unreal,'TranslucencyLightingMode'):print([n for n in dir(unreal.TranslucencyLightingMode) if n.startswith('TLM')])
