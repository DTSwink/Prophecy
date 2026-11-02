"""Headless software-rendered preview QA; never attaches to user's browser."""
import asyncio, base64, json, subprocess, time, urllib.request
from pathlib import Path
import websockets
from repair_slow_targets import ROOT

OUT=ROOT/'Saved/MimicKitSlowLoco/limp-idles-preview-20261101'
URL='http://127.0.0.1:8863/Saved/MimicKitSlowLoco/limp-idles-preview-20261101/'

async def inspect(endpoint):
    errors=[]
    async with websockets.connect(endpoint,max_size=32*1024*1024) as ws:
        seq=0
        async def call(method,params=None):
            nonlocal seq
            seq+=1;ident=seq;await ws.send(json.dumps(dict(id=ident,method=method,params=params or {})))
            while True:
                item=json.loads(await ws.recv())
                if item.get('method')=='Runtime.exceptionThrown':errors.append(item['params'])
                if item.get('id')==ident:
                    assert 'error' not in item,item
                    return item.get('result',{})
        async def evaluate(expression):
            result=await call('Runtime.evaluate',dict(expression=expression,returnByValue=True,awaitPromise=True))
            assert 'exceptionDetails' not in result,result
            return result.get('result',{}).get('value')
        await call('Page.enable');await call('Runtime.enable')
        await call('Emulation.setDeviceMetricsOverride',dict(width=1500,height=1100,deviceScaleFactor=1,mobile=False))
        await call('Page.navigate',dict(url=URL))
        for _ in range(100):
            if await evaluate('Boolean(window.idlePreview)'):break
            await asyncio.sleep(.2)
        assert await evaluate('Boolean(window.idlePreview)'),errors
        async def screenshot(name):
            await asyncio.sleep(.2)
            r=await call('Page.captureScreenshot',dict(format='png',captureBeyondViewport=False))
            (OUT/name).write_bytes(base64.b64decode(r['data']))
        await screenshot('preview.png')
        await evaluate("document.querySelector('[data-view=front]').click()")
        await screenshot('front.png')
        await evaluate("document.querySelector('[data-view=side]').click()")
        await screenshot('side.png')
        await evaluate("document.getElementById('play').click()")
        await asyncio.sleep(.65)
        advanced=await evaluate('idlePreview.time');assert advanced>.15,advanced
        async def space():
            await call('Input.dispatchKeyEvent',dict(type='keyDown',key=' ',code='Space',windowsVirtualKeyCode=32))
            await call('Input.dispatchKeyEvent',dict(type='keyUp',key=' ',code='Space',windowsVirtualKeyCode=32))
        await space();assert not await evaluate('idlePreview.playing')
        stopped=await evaluate('idlePreview.time');await asyncio.sleep(.35)
        assert await evaluate('idlePreview.time')==stopped
        await evaluate("(()=>{const s=document.getElementById('time');s.value=idlePreview.duration-.08;s.dispatchEvent(new Event('input'));})()")
        await space();assert await evaluate('idlePreview.playing')
        await asyncio.sleep(.5);wrapped=await evaluate('idlePreview.time');assert 0<=wrapped<1.,wrapped
        await space()
        await evaluate("document.querySelector('[data-view=three]').click()")
        assert not errors,errors
        result=dict(url=URL,headless=True,software_rendering=True,page_errors=errors,button_advanced_seconds=advanced,
            space_pause=True,paused_time_constant=True,space_resume=True,loop_wrapped_to_seconds=wrapped)
        (OUT/'viewer-check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

def main():
    profile=OUT/'headless-profile';profile.mkdir(exist_ok=True)
    (profile/'DevToolsActivePort').unlink(missing_ok=True)
    proc=subprocess.Popen([r'C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu',
        '--use-angle=swiftshader','--enable-unsafe-swiftshader','--no-first-run','--no-default-browser-check',
        '--remote-debugging-port=0','--remote-allow-origins=*','--user-data-dir='+str(profile),'about:blank'],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(100):
            portfile=profile/'DevToolsActivePort'
            if portfile.exists():break
            time.sleep(.1)
        port=int(portfile.read_text().splitlines()[0])
        targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
        target=next(x for x in targets if x['type']=='page')
        asyncio.run(inspect(target['webSocketDebuggerUrl']))
    finally:
        proc.terminate();proc.wait(timeout=15)

if __name__=='__main__':main()
