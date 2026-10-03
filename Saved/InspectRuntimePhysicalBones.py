import collections
import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    class_name = actor.get_class().get_name()
    if not any(token in class_name for token in ["BP_ProphecyManualPoseAgent", "SandboxCharacter_CMC"]):
        continue
    for name in ["physical_bones", "physical bones"]:
        try:
            bones = [str(value) for value in actor.get_editor_property(name)]
            counts = collections.Counter(bones)
            duplicates = {bone: count for bone, count in counts.items() if count > 1}
            print("{} property={!r} count={} unique={} duplicates={} bones={}".format(
                actor.get_name(), name, len(bones), len(counts), duplicates, bones))
            break
        except Exception:
            pass

