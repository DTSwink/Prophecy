import importlib.util
import json
import os

import unreal

BODY = "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody"
BLUEPRINT = "/Game/_mygame/MetaHumans/BP_test_UEFNDirect"
SOURCE_BLUEPRINT = "/Game/MetaHumans/test_UEFNExactFull/BP_test_UEFNExactFull"
FACE_ANIM = "/Game/MetaHumans/Common/Face/Face_AnimBP"

script = os.path.join(
    unreal.Paths.project_dir(), "Tools", "MetaHuman", "build_uefn_direct_metahuman.py"
)
spec = importlib.util.spec_from_file_location("build_uefn_direct_metahuman", script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Overwrite the existing default body's LOD0 weights in place with the
# fitted weights and regenerate LODs; asset identity and references survive.
module._apply_reduced_weights(BODY)

if not unreal.EditorAssetLibrary.does_asset_exist(BLUEPRINT):
    unreal.SystemLibrary.execute_console_command(
        None,
        "Prophecy.MetaHuman.BuildUEFNBlueprint {} {} {} {}".format(
            SOURCE_BLUEPRINT, BODY, FACE_ANIM, BLUEPRINT
        ),
    )
if not unreal.EditorAssetLibrary.does_asset_exist(BLUEPRINT):
    raise RuntimeError("Default Blueprint was not regenerated")

import argparse
args = argparse.Namespace(body_output=BODY, blueprint_output=BLUEPRINT, reuse_existing=True)
module._audit(args)
print("PROMOTION_DONE")
