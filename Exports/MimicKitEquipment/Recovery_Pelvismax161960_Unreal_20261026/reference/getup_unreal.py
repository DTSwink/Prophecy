"""Run the frozen policy against the installed Jolt DLL inside a headless UE test."""
from getup_transfer import *

class Channel:
    def __init__(self):
        self.directory=OUT/f'unreal-ipc-{int(time.time())}';self.directory.mkdir();self.sequence=0
        command=['C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe',
            str(ROOT/'GameAnimationSample3.uproject'),'/Engine/Maps/Entry','-nullrhi','-nocef','-unattended',
            '-nosplash','-nosound','-NoLiveCoding','-ExecCmds=Automation RunTests Prophecy.Jolt.RecoveryTransfer',
            '-TestExit=Automation Test Queue Empty',f'-RecoveryAuditDir={self.directory}',f'-abslog={self.directory}/unreal.log']
        self.process=subprocess.Popen(command,creationflags=subprocess.CREATE_NO_WINDOW)
    def request(self,command):
        request=self.directory/f'request_{self.sequence}.txt';temp=request.with_suffix('.tmp');temp.write_text(command);temp.replace(request)
        response=self.directory/f'response_{self.sequence}.json';deadline=time.monotonic()+150
        while True:
            try:
                result=json.loads(response.read_text(encoding='utf-8-sig'));break
            except (FileNotFoundError,PermissionError):pass
            if self.process.poll() is not None:raise RuntimeError(f'Unreal exited {self.process.returncode}; see {self.directory}/unreal.log')
            if time.monotonic()>deadline:raise TimeoutError(f'Unreal response missing: {response}')
            time.sleep(.002)
        self.sequence+=1;return result

class UnrealJolt:
    channel=None
    backend_label='Unreal automation: installed project Jolt DLL, isolated 15-body physics world'
    def __init__(self,state):
        path=self.channel.directory/'initial.txt';np.savetxt(path,state,fmt='%.12g')
        self.initial=self.request('reset '+str(path))
    def request(self,command):return self.channel.request(command)
    def close(self):pass

if __name__=='__main__':
    import getup_transfer
    parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',default='native');parser.add_argument('--rows',default='3,8,9,16');parser.add_argument('--label',default='unreal-installed');args=parser.parse_args()
    channel=Channel();UnrealJolt.channel=channel;getup_transfer.Jolt=UnrealJolt
    try:getup_transfer.jolt_test(args.checkpoint,list(map(int,args.rows.split(','))),args.label)
    finally:
        if channel.process.poll() is None:
            channel.request('quit');channel.process.wait(60)
    assert channel.process.returncode==0,channel.process.returncode
    print('Unreal automation completed:',channel.directory,flush=True)
