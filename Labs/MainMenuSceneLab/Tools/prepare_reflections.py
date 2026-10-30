"""Rebuild only water and softbox materials; use UnrealEditor-Cmd -run=pythonscript."""
import pathlib
base=pathlib.Path(__file__).parent
# The shared preamble defines guarded material helpers without running builders.
source=(base/'prepare_materials.py').read_text(encoding='utf-8')
exec(source.split("\nnoise=",1)[0],globals())
water=source.split("\nm=material('M_Water')",1)[1].split("\nm=material('M_Mannequin')",1)[0]
exec("m=material('M_Water')"+water,globals())
exec((base/'softbox_material.py').read_text(encoding='utf-8'),globals())
print('DISTANCE_REFLECTION_MATERIALS_READY')
