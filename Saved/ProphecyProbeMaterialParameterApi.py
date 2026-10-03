import unreal


material = unreal.load_asset("/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Materials/MI_Face_Skin_LOD1")
unreal.log("[ProphecyMaterialParameterApi] MaterialEditingLibrary methods " + str([
    name for name in dir(unreal.MaterialEditingLibrary)
    if "parameter" in name.lower() or "texture" in name.lower() or "instance" in name.lower()
]))
unreal.log("[ProphecyMaterialParameterApi] instance methods " + str([
    name for name in dir(material)
    if "parameter" in name.lower() or "texture" in name.lower() or "parent" in name.lower()
]))
