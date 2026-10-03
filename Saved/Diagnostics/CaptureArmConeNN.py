import pathlib
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
src=(p/'CaptureArmConeCurrent.py').read_text().replace('arm_cone_million_before','arm_cone_nn')
exec(compile(src,'CaptureArmConeNN','exec'))
