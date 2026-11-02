#pragma once
#include "CoreMinimal.h"
struct FSceneMenuParameter {const TCHAR* Key; float Default,Min,Max;};
inline const FSceneMenuParameter SceneMenuParameters[]={
{TEXT("menu_enabled"),1.0000f,0.0000f,1.0000f},
{TEXT("menu_x"),112.0000f,0.0000f,1000.0000f},
{TEXT("menu_y"),66.0000f,0.0000f,600.0000f},
{TEXT("menu_width"),400.0000f,260.0000f,650.0000f},
{TEXT("menu_height"),544.0000f,400.0000f,680.0000f},
{TEXT("menu_scale"),1.0000f,0.6000f,1.3000f},
{TEXT("menu_top"),129.0000f,60.0000f,200.0000f},
{TEXT("menu_row_spacing"),66.0000f,42.0000f,90.0000f},
{TEXT("menu_font_size"),34.0000f,20.0000f,44.0000f},
{TEXT("menu_tracking"),3.0000f,0.0000f,6.0000f},
{TEXT("menu_selected_scale"),1.2500f,1.0000f,1.5000f},
{TEXT("menu_panel_opacity"),0.6600f,0.0000f,1.0000f},
{TEXT("menu_border_opacity"),1.0000f,0.0000f,1.0000f},
{TEXT("menu_border_width"),1.5000f,0.5000f,3.0000f},
{TEXT("menu_ornament_scale"),1.0000f,0.5000f,1.8000f},
{TEXT("menu_glow"),1.0000f,0.0000f,2.0000f},
{TEXT("menu_red"),0.6500f,0.0000f,1.0000f},
{TEXT("menu_text_brightness"),1.0000f,0.4000f,1.3000f},
{TEXT("menu_motion"),0.3500f,0.0000f,1.0000f},
{TEXT("menu_selected"),0.0000f,0.0000f,4.0000f}
};
