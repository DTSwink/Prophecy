import unreal

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for name in dir(subsystem):
    if "duplicate" in name.lower() or "spawn" in name.lower():
        member = getattr(subsystem, name)
        print(name + "=" + str(getattr(member, "__doc__", "")).splitlines()[0])
