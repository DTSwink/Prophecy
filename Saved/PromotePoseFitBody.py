import importlib.util
import os

import unreal

BODY = "/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody"
BLUEPRINT = "/Game/_mygame/MetaHumans/BP_test_UEFNDirect"

for path in (BLUEPRINT, BODY):
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        if not unreal.EditorAssetLibrary.delete_asset(path):
            raise RuntimeError("Could not delete old default asset: " + path)
        print("DELETED|" + path)

script = os.path.join(
    unreal.Paths.project_dir(), "Tools", "MetaHuman", "build_uefn_direct_metahuman.py"
)
spec = importlib.util.spec_from_file_location("build_uefn_direct_metahuman", script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.main()
print("PROMOTION_BUILD_AND_AUDIT_DONE")
