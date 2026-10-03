import pathlib
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
src=(p/'CaptureHand180.py').read_text().replace("tag='hand180'","tag='arm_revolution_current'").replace("s['frame']>=235","s['frame']>=330")
exec(compile(src,'CaptureArmRevolution','exec'))
