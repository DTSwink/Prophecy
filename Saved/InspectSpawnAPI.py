import unreal

for owner in (unreal.GameplayStatics, unreal.Actor, unreal.SystemLibrary):
    print(str(owner) + "=" + ",".join(name for name in dir(owner) if "spawn" in name.lower()))
world = unreal.EditorLevelLibrary.get_game_world()
print("WORLD=" + ",".join(name for name in dir(world) if "spawn" in name.lower()))
