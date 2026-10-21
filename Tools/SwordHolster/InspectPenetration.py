"""Read-only current sword graph, scene and runtime state."""
import json, pathlib, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
out = pathlib.Path(unreal.Paths.project_saved_dir()) / "Diagnostics/SwordSkeletonPenetration"
out.mkdir(parents=True, exist_ok=True)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), "Prophecy.Sword.AuditCollisionGraph")
source = pathlib.Path(unreal.Paths.project_saved_dir()) / "Diagnostics/SwordThigh/BlueprintGraph.txt"
raw = source.read_bytes()
text = raw.decode("utf-16" if raw.startswith(b"\xff\xfe") else "utf-8-sig")
blocks = text.split("\n\n")
(out / "sword-graph.txt").write_text("\n\n".join(b for b in blocks if b.lstrip().startswith("/Game/_mygame/sword/")), encoding="utf-8")
data = {"world": ed.get_editor_world().get_path_name(), "play": bool(ed.get_game_world()), "actors": []}
for world in [ed.get_editor_world(), ed.get_game_world()]:
    if not world:
        continue
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        if "sword" not in a.get_class().get_name().lower() and not isinstance(a, unreal.SkeletalMeshActor):
            continue
        entry = {"actor": a.get_path_name(), "label": a.get_actor_label(), "class": a.get_class().get_name(),
                 "location": str(a.get_actor_location()), "components": []}
        for c in a.get_components_by_class(unreal.ActorComponent):
            item = {"component": c.get_name(), "class": c.get_class().get_name()}
            if isinstance(c, unreal.PrimitiveComponent):
                item.update(collision=str(c.get_collision_enabled()), profile=str(c.get_collision_profile_name()),
                            object_type=str(c.get_collision_object_type()), sim=c.is_simulating_physics(),
                            responses={str(ch): str(c.get_collision_response_to_channel(ch)) for ch in
                                       [unreal.CollisionChannel.ECC_WORLD_STATIC, unreal.CollisionChannel.ECC_WORLD_DYNAMIC,
                                        unreal.CollisionChannel.ECC_PHYSICS_BODY, unreal.CollisionChannel.ECC_VISIBILITY]})
            entry["components"].append(item)
        if "sword" in a.get_class().get_name().lower():
            for name in ["current vel", "current tip vel", "current ang vel", "current location", "current rotation"]:
                try:
                    entry[name] = str(a.get_editor_property(name))
                except Exception:
                    pass
        data["actors"].append(entry)
(out / "state.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
print(json.dumps(data))

