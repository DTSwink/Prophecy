import unreal

skeleton = unreal.load_asset(
    "/Game/MetaHumans/Common/Female/Medium/NormalWeight/Body/metahuman_base_skel"
)
names = [n for n in dir(skeleton) if "retarget" in n.lower() or "translation" in n.lower()]
print("SKEL_FUNCS|{}".format(names))
lib_names = [n for n in dir(unreal.AnimationLibrary) if "retarget" in n.lower()]
print("ANIMLIB|{}".format(lib_names))
candidates = []
for module_name in dir(unreal):
    if "skeleton" in module_name.lower():
        candidates.append(module_name)
print("CLASSES|{}".format(candidates))
