"""Read-only PIE registration/pose audit. Does not change agents or save assets."""
import json
import math
import time
import traceback
from pathlib import Path
import unreal


def game_world():
    return (unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            or unreal.EditorLevelLibrary.get_game_world())


world = game_world()
assert world, "Start PIE with the placed agents first"
agents = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent))
managers = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyNNLocomotionManager))
assert len(managers) == 1, f"Expected one shared manager, found {len(managers)}"
assert len(agents) >= 2, f"Expected at least two placed agents, found {len(agents)}"
manager = managers[0]
controller = unreal.GameplayStatics.get_player_controller(world, 0)
state = {"callback": None, "next_sample": 0.0, "samples": []}
output = Path(unreal.Paths.project_saved_dir()).resolve() / "NNRegistration/placed_agents.json"


def vec(v):
    return [v.x, v.y, v.z]


def read_agent(agent):
    handle = agent.get_agent_handle()
    source = agent.get_nn_pose_data_source()
    pose = agent.read_nn_future_world_pose()
    assert agent.has_valid_agent_handle(), agent.get_name() + " has no handle"
    assert manager.resolve_agent(handle) == agent, agent.get_name() + " does not resolve"
    assert source is not None and pose is not None, agent.get_name() + " has no NN data"
    names, future, presented, alpha = pose
    # Physical mode returns the PHAT's body set, not necessarily all 25 NN bones.
    assert len(names) >= 9 and len(future) == len(names), "Incomplete pose"
    positions = {str(name): vec(transform.translation) for name, transform in zip(names, future)}
    assert all(math.isfinite(v) for p in positions.values() for v in p), "Non-finite target"
    mesh = agent.get_pose_reference_mesh()
    pelvis = mesh.get_socket_transform('pelvis', unreal.RelativeTransformSpace.RTS_WORLD)
    return {
        "actor": agent.get_name(), "lane": handle.index, "generation": handle.generation,
        "pose_id": source[0], "pose_interval": source[1],
        "inference_enabled": agent.is_nn_inference_enabled(),
        "tick_enabled": agent.is_actor_tick_enabled(),
        "mode": str(agent.get_simulation_mode()),
        "root_cm": vec(agent.get_actor_location()),
        "physical_pelvis_cm": vec(pelvis.translation),
        "targets_cm": positions,
    }


def finish(error=None):
    if state["callback"] is not None:
        unreal.unregister_slate_post_tick_callback(state["callback"])
        state["callback"] = None
    summary = []
    if not error:
        first = state["samples"][0]["agents"]
        for i, initial in enumerate(first):
            maximum_change = max(
                math.dist(initial["targets_cm"][bone], sample["agents"][i]["targets_cm"][bone])
                for sample in state["samples"] for bone in initial["targets_cm"])
            if maximum_change <= 1e-5:
                error = f"{initial['actor']} never published a changed pose"
            summary.append({"actor": initial["actor"], "lane": initial["lane"],
                            "pose_id": initial["pose_id"], "max_target_change_cm": maximum_change})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"passed": error is None, "error": error,
        "manager": manager.get_name(), "crowd_size": manager.get_editor_property('crowd_size'),
        "possessed": controller.get_controlled_pawn().get_name() if controller and controller.get_controlled_pawn() else None,
        "summary": summary, "samples": state["samples"]}, indent=2))
    unreal.log("Placed agent registration audit: " + str(output) + " error=" + str(error))


def sample(_delta):
    try:
        now = time.monotonic()
        if now < state["next_sample"]:
            return
        assert game_world() == world, "PIE ended during audit"
        rows = [read_agent(agent) for agent in agents]
        assert len({row['lane'] for row in rows}) == len(rows), "Shared agent lane"
        assert len({row['pose_id'] for row in rows}) == len(rows), "Shared pose store ID"
        state["samples"].append({"world_time": unreal.GameplayStatics.get_time_seconds(world), "agents": rows})
        state["next_sample"] = now + 0.25
        if len(state["samples"]) >= 20:
            finish()
    except Exception:
        finish(traceback.format_exc())


state["callback"] = unreal.register_slate_post_tick_callback(sample)
print("Sampling all placed agents for five seconds; no inputs/settings changed")
