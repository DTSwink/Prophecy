import unreal
for p in [
'/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor_Animated_CM1',
'/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor_Animated_CM2',
'/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Basecolor_Animated_CM3',
'/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal_Animated_WM1',
'/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal_Animated_WM2',
'/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/Textures/T_Face_Normal_Animated_WM3',
'/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Basecolor',
'/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Body/Textures/T_Normal']:
    t=unreal.load_asset(p)
    print(p, 'vt=', t.get_editor_property('virtual_texture_streaming') if t else None, 'srgb=', t.get_editor_property('srgb') if t else None)
