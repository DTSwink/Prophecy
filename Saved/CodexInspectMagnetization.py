import sys
import unreal

worlds = unreal.EditorLevelLibrary.get_pie_worlds(False)
if not worlds:
    raise RuntimeError("No PIE world")
world = worlds[0]
print(f"CODEX_WORLD_GRAVITY={world.get_gravity_z()}")
cls = unreal.load_class(None, "/Script/GameAnimationSample3.ProphecyAgent")
agent = unreal.GameplayStatics.get_all_actors_of_class(world, cls)[0]
mesh = agent.get_pose_reference_mesh()
print(f"CODEX_MESH_GRAVITY={mesh.is_gravity_enabled()}")
if len(sys.argv) > 1 and sys.argv[1] == "setzero":
    agent.set_all_body_magnetization(True, 0.0, 1.0)
    print("CODEX_CALLED_SET_ALL_ZERO")
if len(sys.argv) > 1 and sys.argv[1] == "setoff":
    agent.set_all_body_magnetization(True, 0.0, 0.0)
    print("CODEX_CALLED_SET_ALL_OFF")
if len(sys.argv) > 1 and sys.argv[1] == "move":
    low = agent.get_root_low_point()
    agent.teleport_managed_root_low_point(low + unreal.Vector(100.0, 0.0, 0.0), agent.get_actor_rotation().yaw)
    print("CODEX_MOVED_ROOT_100_CM")
print(f"CODEX_GLOBAL_ENABLED={agent.get_editor_property('bWorldMagnetizationEnabled')}")
print(f"CODEX_GLOBAL_LINEAR={agent.get_editor_property('WorldMagnetizationLinearStrengthScale')}")
print(f"CODEX_GLOBAL_ANGULAR={agent.get_editor_property('WorldMagnetizationAngularStrengthScale')}")
for bone in ["pelvis", "thigh_l", "foot_l", "upperarm_r"]:
    try:
        print(f"CODEX_SETTING {bone}={agent.get_body_magnetization_settings(bone)}")
        print(f"CODEX_STATE {bone}={agent.get_physical_body_state(bone)}")
    except Exception as exc:
        print(f"CODEX_ERROR {bone}={exc}")
