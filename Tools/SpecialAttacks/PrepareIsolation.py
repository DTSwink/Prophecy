"""Copy the current working source and only required assets to an existing worktree."""
import hashlib
import json
import pathlib
import shutil
import sys

source = pathlib.Path(__file__).resolve().parents[2]
dest = pathlib.Path(sys.argv[1]).resolve()
assert (dest / ".git").is_file() and dest != source
receipt = dest / "Saved/SpecialAttacks/baseline.json"
if receipt.exists():
    raise SystemExit("Already prepared; refusing to overwrite isolated edits.")
hashes = {}
def copy(path):
    rel = path.relative_to(source)
    target = dest / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    hashes[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()

for folder in ["Source", "Plugins/ProphecyJolt/Source", "Plugins/ProphecyJolt/Config",
               "StandaloneSim/sim_core/include", "Tools/Jolt/Patches", "Tools/SpecialAttacks",
               "Content/locomotion/NN"]:
    for path in (source / folder).rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            copy(path)
for path in (source / "Config").glob("Default*.ini"):
    copy(path)
copy(source / "GameAnimationSample3.uproject")
copy(source / "Plugins/ProphecyJolt/ProphecyJolt.uplugin")
assets = json.loads((source / "Saved/Diagnostics/SpecialAttacks/assets.json").read_text())
for package in assets["packages"]:
    path = source / "Content" / (package[6:] + ".uasset")
    if path.exists():
        copy(path)
# Prepared dependency is a small immutable input; copy, never link live output directories.
shutil.copytree(source / "Intermediate/JoltMigration/Install/Development",
                dest / "Intermediate/JoltMigration/Install/Development", dirs_exist_ok=True)
receipt.parent.mkdir(parents=True, exist_ok=True)
receipt.write_text(json.dumps({"source": str(source), "files": hashes, "clips": assets["clips"]},
                              indent=2))
print(json.dumps({"copied_files": len(hashes), "worktree": str(dest)}))
