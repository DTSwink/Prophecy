import sys
import time


sys.path.insert(
    0,
    r"C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental"
    r"\PythonScriptPlugin\Content\Python",
)
import remote_execution


CODE = r'''
import unreal

animation_path = "/Game/Characters/UEFN_Mannequin/Animations/Sprint/M_Neutral_Sprint_Loop_F_L_20"
source_mesh = unreal.load_asset("/Game/_mygame/SKM_UEFN_Mannequin")
target_mesh = unreal.load_asset("/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh")
retargeter = unreal.load_asset("/Game/MetaHumans/Common/Common/Rigs/RTG_UEFN_to_Metahuman_nrw")
asset_subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
asset_data = asset_subsystem.find_asset_data(animation_path)
if not source_mesh or not target_mesh or not retargeter or not asset_data.is_valid():
    raise RuntimeError("Missing hand-audit retarget input")

results = unreal.IKRetargetBatchOperation.duplicate_and_retarget(
    [asset_data],
    source_mesh,
    target_mesh,
    retargeter,
    search="",
    replace="",
    prefix="",
    suffix="_MHHandAudit",
    include_referenced_assets=False,
    overwrite_existing_files=True,
)
if not results:
    raise RuntimeError("IK Retargeter produced no diagnostic animation")
for result in results:
    asset = result.get_asset()
    print("HAND_AUDIT_RETARGET=" + asset.get_path_name())
'''


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
        CODE,
        unattended=True,
        exec_mode=remote_execution.MODE_EXEC_FILE,
    )
    if not result.get("success"):
        raise RuntimeError(result.get("result", "Remote retarget failed"))
    for entry in result.get("output", []):
        print(entry.get("output", ""))
finally:
    remote.stop()
