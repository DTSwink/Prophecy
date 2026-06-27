import json
import math
import traceback

import unreal


def run():
    payload = {
        "renderer_class": None,
        "library_class": None,
        "spawned": False,
        "active_stains": None,
        "total_stains": None,
        "errors": [],
    }

    renderer_class = unreal.load_class(None, "/Script/GameAnimationSample3.ProphecyBloodStainRenderer")
    library_class = unreal.load_class(None, "/Script/GameAnimationSample3.ProphecyBloodStainBlueprintLibrary")
    payload["renderer_class"] = str(renderer_class)
    payload["library_class"] = str(library_class)

    try:
        world = unreal.EditorLevelLibrary.get_editor_world()
    except Exception as exc:
        payload["errors"].append(f"get_editor_world failed: {exc!r}")
        world = None

    if world and renderer_class:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(renderer_class, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
        payload["spawned"] = actor is not None
        if actor:
            for i in range(24):
                angle = (math.pi * 2.0 * i) / 24.0
                pos = unreal.Vector(math.cos(angle) * 120.0, math.sin(angle) * 120.0, 8.0)
                normal = unreal.Vector(0.0, 0.0, 1.0)
                actor.add_blood_hit(pos, normal, 8.0, unreal.LinearColor(0.12, 0.0, 0.0, 1.0))
            actor.flush_pending_stains()
            payload["active_stains"] = actor.get_editor_property("active_stain_count")
            payload["total_stains"] = actor.get_editor_property("total_stains_accepted")
            unreal.EditorLevelLibrary.destroy_actor(actor)

    return payload


try:
    result = run()
except Exception:
    result = {"fatal": traceback.format_exc()}

print("PROPHECY_BLOOD_RENDERER_VERIFY_BEGIN")
print(json.dumps(result, indent=2, default=str))
print("PROPHECY_BLOOD_RENDERER_VERIFY_END")
