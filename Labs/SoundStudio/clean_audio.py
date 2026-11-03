"""Local Antinode Clear Strong preset, isolated from the GUI process."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time
import numpy as np

PRESET = 'Clear strong: ambience -24 dB, voice reverb -12 dB, voice 0 dB; Eco off.'


def plugin_path():
    config_path=Path(__file__).with_name('runtime.json')
    config=json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
    default=Path(os.environ.get('CommonProgramFiles',r'C:\Program Files\Common Files'))/'VST3'/'Clear.vst3'
    path=Path(config.get('clear_plugin',default))
    if not path.exists():
        raise RuntimeError('Clean needs the installed Antinode Clear VST3 plug-in. Install or activate Clear, then try again.')
    return path


def level_match(dry,wet,rate):
    """The comparison's active-RMS match, without its extra listening boost."""
    hop=max(1,round(rate*.01));frames=len(dry)
    # Include the final partial block, and share the detector between channels.
    power=np.mean(dry.astype(np.float64)**2,axis=1)
    starts=np.arange(0,frames,hop)
    lengths=np.minimum(hop,frames-starts)
    rms=np.sqrt(np.add.reduceat(power,starts)/lengths)
    active=np.repeat(rms>10**(-45/20),lengths)
    if not np.any(active):return wet,1.
    target=np.sqrt(np.mean(dry[active].astype(np.float64)**2))
    current=np.sqrt(np.mean(wet[active].astype(np.float64)**2))
    peak=float(np.max(np.abs(wet),initial=0))
    if current<=1e-12 or peak<=1e-12:return wet,1.
    gain=min(target/current,10**(-1.5/20)/peak)
    return wet*np.float32(gain),gain


def render_plugin(samples,rate,path):
    from pedalboard import load_plugin
    peak=float(np.max(np.abs(samples),initial=0))
    if peak<=1e-9:return samples.copy(),{'silent':True}
    gain=10**(-3/20)/peak
    dry=samples*np.float32(gain)
    plugin=load_plugin(str(path))
    plugin.ambience_gain=-24.;plugin.voice_reverb_gain=-12.;plugin.voice_gain=0.
    plugin.ecomode=False;plugin.mono_or_stereo=False;plugin.bypass=False
    for stem in ('ambience','voice','voice_reverb'):
        for flag in ('solo','mute','diff'):setattr(plugin,stem+'_'+flag,False)
    # One continuous plugin pass, never reset between chunks. Licensing/trial
    # behavior is left intact. Padding flushes endings, not the plugin's timer.
    padded=np.pad(dry,((0,rate//2),(0,0)))
    wet=plugin(np.ascontiguousarray(padded.T),rate,buffer_size=1024,reset=True).T
    if wet.shape[1]!=samples.shape[1] or len(wet)<len(samples):
        raise RuntimeError('Clear did not return the complete sound.')
    wet=np.ascontiguousarray(wet[:len(samples)])
    if not np.isfinite(wet).all():raise RuntimeError('Clear returned invalid audio.')
    wet,match=level_match(dry,wet,rate)
    metadata={'preset':PRESET,'version':str(plugin.version),
              'reported_latency_samples':plugin.reported_latency_samples,
              'level_match_db':float(20*np.log10(match))}
    return wet/np.float32(gain),metadata


def clean_source(samples,rate,cancel=None):
    """Return a full-strength, level-matched result at the original frame count."""
    from audio_engine import check_cancel,ffmpeg_filter
    check_cancel(cancel)
    if not np.any(np.abs(samples)>1e-9):return samples.copy(),[PRESET]
    path=plugin_path();work_rate=rate;source=samples
    if rate not in (44100,48000,96000):
        work_rate=48000
        source,_=ffmpeg_filter(samples,rate,['aresample=48000:resampler=soxr:precision=28'],cancel,48000)
    python=Path(sys.executable).with_name('python.exe') if os.name=='nt' else Path(sys.executable)
    if not python.is_file():python=Path(sys.executable)
    with tempfile.TemporaryDirectory(prefix='prophecy-clean-') as directory:
        directory=Path(directory)
        np.save(directory/'input.npy',source,allow_pickle=False)
        command=[str(python),str(Path(__file__).resolve()),str(directory),str(work_rate),str(path)]
        with (directory/'error.txt').open('w+b') as errors:
            process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=errors,
                                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            started=time.monotonic()
            try:
                while process.poll() is None:
                    check_cancel(cancel)
                    if time.monotonic()-started>max(120,10*len(source)/work_rate):
                        raise RuntimeError('Clear took too long. Try a shorter source clip.')
                    time.sleep(.025)
            except BaseException:
                process.kill();process.wait();raise
            if process.returncode:
                errors.seek(0)
                detail=errors.read().decode('utf-8','replace')[-1600:]
                raise RuntimeError('Clean could not run Clear. Check its installation/activation. '+detail)
        result=np.load(directory/'output.npy',allow_pickle=False)
        metadata=json.loads((directory/'result.json').read_text(encoding='utf-8'))
    check_cancel(cancel)
    if work_rate!=rate:
        result,_=ffmpeg_filter(result,work_rate,[f'aresample={rate}:resampler=soxr:precision=28'],cancel,rate)
    if result.shape[1]!=samples.shape[1] or abs(len(result)-len(samples))>1 or not np.isfinite(result).all():
        raise RuntimeError('Clear output could not be aligned to the source.')
    result=np.pad(result,((0,max(0,len(samples)-len(result))),(0,0)))[:len(samples)]
    notes=[PRESET,f'Clear {metadata.get("version","")}; active level matched by {metadata.get("level_match_db",0):+.2f} dB.']
    return np.ascontiguousarray(result),notes


if __name__=='__main__':
    folder=Path(sys.argv[1]);rate=int(sys.argv[2]);path=Path(sys.argv[3])
    result,metadata=render_plugin(np.load(folder/'input.npy',allow_pickle=False),rate,path)
    np.save(folder/'output.npy',result,allow_pickle=False)
    (folder/'result.json').write_text(json.dumps(metadata),encoding='utf-8')
