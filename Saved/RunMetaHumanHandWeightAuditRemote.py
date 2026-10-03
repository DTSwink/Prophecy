import os
import sys
import time


sys.path.insert(
    0,
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python",
)
import remote_execution


script_path = os.path.join(os.path.dirname(__file__), "MetaHumanHandWeightAudit.py")
code = (
    "path = " + repr(script_path) + "\n"
    "with open(path, 'r', encoding='utf-8') as handle:\n"
    "    source = handle.read()\n"
    "exec(compile(source, path, 'exec'))\n"
    "actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()\n"
    "uefn_actor = next(actor for actor in actors if actor.get_actor_label() == 'UEFN_Hand_Audit')\n"
    "meta_actor = next(actor for actor in actors if actor.get_actor_label() == 'MetaHuman_Hand_Audit')\n"
    "uefn_component = uefn_actor.skeletal_mesh_component\n"
    "meta_component = meta_actor.skeletal_mesh_component\n"
    "max_cm = 0.0\n"
    "max_deg = 0.0\n"
    "max_cm_bone = None\n"
    "max_deg_bone = None\n"
    "for bone in snapshot['uefn_reference']['bones']:\n"
    "    name = bone['name']\n"
    "    if name not in kept_names:\n"
    "        continue\n"
    "    a = uefn_component.get_socket_transform(name, unreal.RelativeTransformSpace.RTS_COMPONENT)\n"
    "    b = meta_component.get_socket_transform(name, unreal.RelativeTransformSpace.RTS_COMPONENT)\n"
    "    cm = (a.translation - b.translation).length()\n"
    "    dot = abs(a.rotation.x*b.rotation.x + a.rotation.y*b.rotation.y + a.rotation.z*b.rotation.z + a.rotation.w*b.rotation.w)\n"
    "    dot = max(-1.0, min(1.0, dot))\n"
    "    deg = math.degrees(2.0 * math.acos(dot))\n"
    "    if cm > max_cm:\n"
    "        max_cm, max_cm_bone = cm, name\n"
    "    if deg > max_deg:\n"
    "        max_deg, max_deg_bone = deg, name\n"
    "print(f'HAND_WEIGHT_AUDIT_POSE|max_cm={max_cm:.9f}|max_cm_bone={max_cm_bone}|max_deg={max_deg:.9f}|max_deg_bone={max_deg_bone}')\n"
    "source_mesh = unreal.load_asset('/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh')\n"
    "print('HAND_WEIGHT_AUDIT_SOURCE_PP=' + str(source_mesh.get_editor_property('post_process_anim_blueprint')))\n"
    "print('HAND_WEIGHT_AUDIT_RTG=' + str(unreal.load_asset('/Game/MetaHumans/Common/Common/Rigs/RTG_UEFN_to_Metahuman_nrw')))\n"
)

remote = remote_execution.RemoteExecution()
remote.start()
try:
    deadline = time.monotonic() + 15.0
    while not remote.remote_nodes and time.monotonic() < deadline:
        time.sleep(0.25)
    if not remote.remote_nodes:
        raise RuntimeError("No Unreal remote-execution node was discovered")
    remote.open_command_connection(remote.remote_nodes[0]["node_id"])
    result = remote.run_command(
        code,
        unattended=True,
        exec_mode=remote_execution.MODE_EXEC_FILE,
    )
    if not result.get("success"):
        raise RuntimeError(result.get("result", "Remote audit failed"))
    for entry in result.get("output", []):
        output = entry.get("output", "")
        if "HAND_WEIGHT_AUDIT" in output:
            print(output)
finally:
    remote.stop()
