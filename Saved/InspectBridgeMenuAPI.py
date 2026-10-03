import unreal


menus = unreal.ToolMenus.get()
menu = menus.find_menu("MainFrame.MainMenu.Window")
print("TOOLMENUS_METHODS|" + ",".join(name for name in dir(menus) if "exec" in name.lower() or "menu" in name.lower()))
print("TOOLMENU_METHODS|" + ",".join(name for name in dir(menu) if "entry" in name.lower() or "section" in name.lower()))
print("TOOLMENUENTRY_METHODS|" + ",".join(name for name in dir(unreal.ToolMenuEntry) if "exec" in name.lower() or "action" in name.lower()))
