"""Existing remote Python transport, with an explicit PID selection for shared hosts."""
import pathlib,sys,time,json,os
sys.path.insert(0,r'C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution
root=pathlib.Path(__file__).resolve().parents[2]
pid=int((root/'Saved/Diagnostics/SpearPike20261030/editor.pid').read_text().strip())
host_file=root/'Saved/Diagnostics/SpearPike20261030/host-path.txt'
project_root=pathlib.Path(host_file.read_text().strip()).resolve() if host_file.exists() else root
remote=remote_execution.RemoteExecution();remote.start()
try:
    deadline=time.monotonic()+float(os.environ.get('PROPHECY_SPEAR_CONNECT_TIMEOUT','50'))
    found=False
    while time.monotonic()<deadline and not found:
        for node in remote.remote_nodes:
            # Do not even open a command connection to a different project/lab.
            advertised=node.get('project_root','')
            if advertised and pathlib.Path(advertised).resolve()!=project_root:continue
            remote.open_command_connection(node['node_id'])
            result=remote.run_command('import os; print("OWNED_PID="+str(os.getpid()))',unattended=True,exec_mode=remote_execution.MODE_EXEC_FILE)
            if any(x.get('output','').strip()=='OWNED_PID='+str(pid) for x in result.get('output',[])):
                found=True;break
            remote.close_command_connection()
        if not found:time.sleep(.5)
    if not found:raise RuntimeError('Owned editor PID not found; no project mutations dispatched')
    script=pathlib.Path(sys.argv[1])
    code='import sys\nsys.argv='+repr(sys.argv[1:])+'\n'+script.read_text(encoding='utf-8-sig')
    result=remote.run_command(code,unattended=True,exec_mode=remote_execution.MODE_EXEC_FILE)
    for entry in result.get('output',[]):print(entry.get('output',''))
    if not result.get('success'):raise RuntimeError(result.get('result','Remote execution failed'))
finally:remote.stop()
