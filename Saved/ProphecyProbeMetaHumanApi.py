import unreal

names = sorted(name for name in dir(unreal) if "MetaHuman" in name or "Metahuman" in name)
unreal.log("PROPHECY_METAHUMAN_API_BEGIN")
for name in names:
    unreal.log(f"PROPHECY_METAHUMAN_API {name}")

for candidate in [
    "MetaHumanCharacter",
    "MetaHumanCharacterFactoryNew",
    "MetaHumanCharacterEditorSubsystem",
    "MetaHumanAssetManager",
    "MetaHumanImportOptions",
]:
    obj = getattr(unreal, candidate, None)
    unreal.log(f"PROPHECY_METAHUMAN_CANDIDATE {candidate}={obj}")
    if obj:
        attrs = [name for name in dir(obj) if "build" in name.lower() or "create" in name.lower() or "asset" in name.lower() or "import" in name.lower()]
        for attr in sorted(attrs):
            unreal.log(f"PROPHECY_METAHUMAN_ATTR {candidate}.{attr}")

unreal.log("PROPHECY_METAHUMAN_API_END")
