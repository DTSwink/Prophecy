"""Start the upstream Blender MCP addon in an owned, hidden Blender session."""
from pathlib import Path
import sys, importlib.util
ROOT = Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy')
addon_path = ROOT/'Saved/Diagnostics/ImperialSpear/blender-mcp/addon.py'
spec = importlib.util.spec_from_file_location('spear_blender_mcp', addon_path)
addon = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = addon
spec.loader.exec_module(addon)
addon.register()
import bpy
bpy.context.scene.render.threads_mode = 'FIXED'
bpy.context.scene.render.threads = 3
server = addon.BlenderMCPServer(host='127.0.0.1', port=9876)
bpy.types.blendermcp_server = server
server.start()
print('SPEAR_MCP_BRIDGE_READY', flush=True)
