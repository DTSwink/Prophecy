"""Validate the graph edit without saving; inspect native compile status in its log."""
import json, os, pathlib, sys, unreal
root = pathlib.Path(unreal.Paths.project_dir()).resolve()
os.chdir(root)
world = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
assert world
sys.argv = ["Tools/SwordHolster/InstallSlowStartCap.py"]
exec((root / sys.argv[0]).read_text(encoding="utf-8"), globals())
exec((root / "Tools/SwordHolster/CheckSlowStartGraph.py").read_text(encoding="utf-8"), globals())
print("SLOW_START_OFFLINE_GRAPH_VERIFIED_UNSAVED")
