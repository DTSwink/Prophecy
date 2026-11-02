"""One bounded MCP call through the upstream stdio server, with a local receipt."""
import asyncio, json, os, sys
from pathlib import Path
from datetime import timedelta
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT = Path(__file__).resolve().parents[2]

async def main():
    env = dict(os.environ, BLENDER_HOST='127.0.0.1', BLENDER_PORT='9876',
               DISABLE_TELEMETRY='true', BLENDER_MCP_DISABLE_TELEMETRY='true')
    params = StdioServerParameters(command=sys.executable,
        args=['-m','blender_mcp.server'], env=env)
    async with stdio_client(params) as (r,w):
        async with ClientSession(r,w,read_timeout_seconds=timedelta(seconds=600)) as session:
            await session.initialize()
            arg = sys.argv[1] if len(sys.argv)>1 else 'inspect'
            if arg == 'inspect':
                result = await session.call_tool('get_scene_info',{})
            else:
                script = Path(arg).resolve()
                code = 'exec(compile(open('+repr(str(script))+', encoding="utf-8").read(), '+repr(str(script))+', "exec"))'
                result = await session.call_tool('execute_blender_code', {'code':code})
            report = result.model_dump(mode='json')
            receipt = ROOT/'Saved/Diagnostics/ImperialSpear'/('mcp_'+Path(arg).stem+'.json')
            receipt.write_text(json.dumps(report,indent=2),encoding='utf-8')
            for content in result.content:
                if getattr(content,'text',None): print(content.text)
            if result.isError or any('Error executing code:' in getattr(content,'text','') for content in result.content):
                raise SystemExit(1)

asyncio.run(main())
