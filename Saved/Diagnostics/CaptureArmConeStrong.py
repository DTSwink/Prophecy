import pathlib
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
src=(p/'CaptureArmCone.py').read_text().replace('arm_cone_default','arm_cone_strong').replace('45.,100.,20.','45.,5000.,100.')
exec(compile(src,'CaptureArmConeStrong','exec'))
