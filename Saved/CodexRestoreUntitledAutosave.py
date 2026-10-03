import pathlib
import unreal


autosave = pathlib.Path(
    r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
    r"\Saved\Autosaves\Temp\Untitled_1_Auto5.umap")
if not autosave.is_file():
    raise RuntimeError("Untitled autosave is missing: {}".format(autosave))
loaded = unreal.EditorLoadingAndSavingUtils.load_map(str(autosave))
if not loaded:
    raise RuntimeError("Unreal did not load the Untitled autosave")
print("UNTITLED_AUTOSAVE_RESTORED", autosave)
