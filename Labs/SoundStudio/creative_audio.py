"""Circular edits, envelopes, seeded grains and non-destructive clip assembly."""
from dataclasses import asdict, replace
from pathlib import Path
import json
import math
import os
import subprocess
import tempfile
import time
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def trim_samples(audio, settings):
    n=len(audio.samples)
    a=min(n,round(settings.start*audio.rate))
    b=n if settings.end is None else min(n,round(settings.end*audio.rate))
    if b>a:
        return audio.samples[a:b].copy()
    # Equal endpoints mean one complete revolution, beginning at IN.
    result=np.concatenate((audio.samples[a:],audio.samples[:b if b!=a else a]),axis=0)
    return result if len(result) else audio.samples.copy()


def trim_duration(settings,duration):
    end=duration if settings.end is None else settings.end
    result=end-settings.start if end>settings.start else duration-settings.start+end
    return result or duration


def validate_curve(points,low,high):
    if not 2<=len(points)<=64:
        raise ValueError('An envelope needs 2–64 points.')
    points=np.asarray(points,dtype=float)
    if points.shape!=(len(points),2) or not np.isfinite(points).all():
        raise ValueError('Invalid envelope points.')
    if points[0,0]!=0 or points[-1,0]!=1 or np.any(np.diff(points[:,0])<=0):
        raise ValueError('Envelope times must increase from 0 to 1.')
    if np.any(points[:,1]<low) or np.any(points[:,1]>high):
        raise ValueError('Envelope value is outside its allowed range.')


def envelope_values(points,positions):
    points=np.asarray(points,dtype=float)
    # Smoothstep interpolation has flat derivatives at nodes and no overshoot.
    index=np.clip(np.searchsorted(points[:,0],positions,side='right')-1,0,len(points)-2)
    left,right=points[index],points[index+1]
    t=np.clip((positions-left[:,0])/(right[:,0]-left[:,0]),0,1)
    t=t*t*(3-2*t)
    return left[:,1]+(right[:,1]-left[:,1])*t


def volume_envelope(samples,points):
    if all(p[1]==1 for p in points):return samples
    gain=envelope_values(points,np.linspace(0,1,len(samples))).astype(np.float32)
    return samples*gain[:,None]


def pitch_envelope(samples,rate,points,formants=False,cancel=None):
    from audio_engine import HERE,check_cancel
    if all(p[1]==0 for p in points):return samples
    config=json.loads((HERE/'runtime.json').read_text(encoding='utf-8'))
    executable=config.get('rubberband')
    if not executable or not Path(executable).is_file():
        raise RuntimeError('Pitch-envelope tools are missing. Run SoundStudio/install.ps1 to repair them.')
    check_cancel(cancel)
    # R3 high-consistency streaming follows the curve without restarting at
    # nodes. The CLI compensates its own start delay; extra silence flushes ends.
    padding=rate//4
    padded=np.pad(samples,((padding,padding),(0,0)))
    frames=np.arange(0,len(padded),256)
    positions=np.clip((frames-padding)/max(1,len(samples)-1),0,1)
    shifts=envelope_values(points,positions)
    initial=points[0][1]
    commands='\n'.join(f'{frame} {shift-initial:.9f}'
                       for frame,shift in zip(frames,shifts))
    with tempfile.TemporaryDirectory(prefix='prophecy-pitch-') as directory:
        directory=Path(directory)
        sf.write(directory/'input.wav',padded,rate,subtype='FLOAT')
        (directory/'pitch.txt').write_text(commands,encoding='ascii')
        command=[executable,'-3','--quiet','--no-threads','--centre-focus','--ignore-clipping',
                 '--pitch',str(initial),'--pitchmap','pitch.txt']
        if formants:command.append('--formant')
        command+=['input.wav','output.wav']
        with (directory/'error.txt').open('w+b') as errors:
            process=subprocess.Popen(command,cwd=directory,stdout=subprocess.DEVNULL,stderr=errors,
                                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            started=time.monotonic()
            try:
                while process.poll() is None:
                    check_cancel(cancel)
                    if time.monotonic()-started>600:raise RuntimeError('Pitch rendering exceeded ten minutes. Shorten the clip.')
                    time.sleep(.025)
            except BaseException:
                process.kill();process.wait();raise
            if process.returncode:
                errors.seek(0);raise RuntimeError('Pitch rendering failed: '+errors.read().decode('utf-8','replace')[-2000:])
        result,_=sf.read(directory/'output.wav',dtype='float32',always_2d=True)
    check_cancel(cancel)
    if len(result)<padding+len(samples):
        raise RuntimeError('Pitch automation did not produce the complete clip.')
    return result[padding:padding+len(samples)].copy()


def _sinc_read(samples,positions,step):
    # Windowed sinc interpolation plus ratio-dependent anti-alias filtering.
    taps=np.arange(-11,13)
    cutoff=min(1.,1/max(abs(step),1e-9))*.95
    output=np.empty((len(positions),samples.shape[1]),np.float32)
    for begin in range(0,len(positions),2048):
        pos=positions[begin:begin+2048]
        indices=np.floor(pos).astype(np.int64)[:,None]+taps
        distance=pos[:,None]-indices
        weights=cutoff*np.sinc(cutoff*distance)*np.where(np.abs(distance)<12,.5+.5*np.cos(np.pi*distance/12),0)
        weights/=weights.sum(axis=1,keepdims=True)
        values=samples[indices%len(samples)]
        output[begin:begin+len(pos)]=np.einsum('ij,ijk->ik',weights,values)
    return output


def granular_synthesis(samples,rate,s,cancel=None):
    from audio_engine import check_cancel
    if not s.granular:return samples
    frames=max(1,round(len(samples)*s.grain_length))
    if frames*samples.shape[1]*4>256*1024*1024:
        raise ValueError('Granular output exceeds 256 MB. Reduce Length or trim the source.')
    size=max(16,round(s.grain_ms*rate/1000))
    hop=size/s.grain_density
    grains=math.ceil((frames+2*size)/hop)
    if grains>60000:
        raise ValueError('Too many grains. Increase Size, lower Density or shorten the clip.')
    rng=np.random.default_rng(s.grain_seed)
    # Native polyphase oversampling gives fast band-limited reads for grains
    # at unity/downward pitch. Upward shifts retain the anti-alias sinc path.
    lookup=resample_poly(samples,8,1,axis=0,padtype='wrap',window=('kaiser',8.6)) if samples.nbytes*8<=64*1024*1024 else None
    output=np.zeros((frames,samples.shape[1]),np.float32)
    weight=np.zeros(frames,np.float32)
    window=np.hanning(size).astype(np.float32)
    for centre in np.arange(-size,frames+size,hop):
        check_cancel(cancel)
        centre+=rng.uniform(-.35,.35)*hop*s.grain_scatter
        start=round(centre-size/2)
        a,b=max(0,start),min(frames,start+size)
        if b<=a:continue
        scan=0 if s.grain_freeze else centre/frames
        location=(s.grain_position+scan+rng.uniform(-.5,.5)*s.grain_scatter)*len(samples)
        semitones=rng.uniform(-s.grain_pitch,s.grain_pitch)
        step=2**(semitones/12)*(-1 if rng.random()<s.grain_reverse else 1)
        indices=np.arange(a-start,b-start)
        positions=location+(indices-size/2)*step
        if lookup is not None and abs(step)<=1:
            positions=(positions*8)%len(lookup)
            base=np.floor(positions).astype(np.int64)
            fraction=(positions-base).astype(np.float32)[:,None]
            grain=lookup[base]*(1-fraction)+lookup[(base+1)%len(lookup)]*fraction
        else:grain=_sinc_read(samples,positions,step)
        if samples.shape[1]==2 and s.grain_width:
            pan=rng.uniform(-1,1)*s.grain_width
            grain*=np.array([np.cos((pan+1)*np.pi/4),np.sin((pan+1)*np.pi/4)],np.float32)*np.sqrt(2)
        w=window[indices]
        output[a:b]+=grain*w[:,None]
        weight[a:b]+=w
    # Normalize overlap, not the recording's loudness. Sparse grains retain gaps.
    output/=np.maximum(1,weight[:,None])
    return output


def stitch_clips(clips,joins,cancel=None):
    """Assemble rendered clips at the first clip's rate, retaining provenance."""
    from audio_engine import Audio,check_cancel,ffmpeg_filter
    if not clips:raise ValueError('Add at least one clip to the sequence.')
    rate=clips[0][1]
    channels=max(x.shape[1] for x,_,_ in clips)
    prepared=[]
    for samples,sample_rate,source in clips:
        check_cancel(cancel)
        if sample_rate!=rate:
            samples,_=ffmpeg_filter(samples,sample_rate,[f'aresample={rate}:resampler=soxr:precision=28'],cancel,rate)
        if samples.shape[1]<channels:samples=np.repeat(samples,channels,axis=1)
        prepared.append(samples)
    overlaps=[]
    for i,(milliseconds,curve) in enumerate(joins):
        if not 0<=milliseconds<=10000 or curve not in ('Equal gain','Equal power'):
            raise ValueError('Invalid crossfade.')
        # Keep each join within half of each neighbouring clip: three-way
        # accidental overlaps cannot consume a short middle clip.
        overlaps.append(min(round(milliseconds*rate/1000),len(prepared[i])//2,len(prepared[i+1])//2))
    length=sum(len(x) for x in prepared)-sum(overlaps)
    if length*channels*4>256*1024*1024:raise ValueError('Sequence exceeds 256 MB. Remove or trim some clips.')
    result=np.zeros((length,channels),np.float32)
    cursor=0;markers=[]
    for i,samples in enumerate(prepared):
        check_cancel(cancel)
        overlap=overlaps[i-1] if i else 0
        start=cursor-overlap
        if overlap:
            t=np.linspace(0,1,overlap,dtype=np.float32) if overlap>1 else np.array([.5],np.float32)
            outgoing,incoming=(np.cos(t*np.pi/2),np.sin(t*np.pi/2)) if joins[i-1][1]=='Equal power' else (1-t,t)
            result[start:cursor]*=outgoing[:,None]
            result[start:cursor]+=samples[:overlap]*incoming[:,None]
        result[cursor:start+len(samples)]=samples[overlap:]
        markers.append({'name':clips[i][2].path.name,'start':start/rate,'end':(start+len(samples))/rate,'overlap':overlap/rate})
        cursor=start+len(samples)
    return result,rate,markers


def variant_settings(settings,count,amount,seed):
    if not 1<=count<=32 or not 0<=amount<=1:raise ValueError('Use 1–32 takes and 0–100% variation.')
    rng=np.random.default_rng(seed)
    variants=[]
    for index in range(count):
        variants.append(replace(settings,grain_seed=int(rng.integers(0,2**31-1)),
                                pitch=float(np.clip(settings.pitch+rng.uniform(-2,2)*amount,-12,12)),
                                gain_db=float(np.clip(settings.gain_db+rng.uniform(-2,2)*amount,-24,18))))
    return variants


def rename_wav(path,name):
    from audio_engine import output_stem,atomic_json
    path=Path(path);destination=path.with_name(output_stem(name)+'.wav')
    if destination==path:return path
    old_recipe=path.with_suffix('.recipe.json');new_recipe=destination.with_suffix('.recipe.json')
    if destination.exists() or new_recipe.exists():raise ValueError('That name already exists. Choose another name.')
    recipe=json.loads(old_recipe.read_text(encoding='utf-8')) if old_recipe.exists() else None
    moved_recipe=False
    os.rename(path,destination)
    try:
        if recipe is not None:
            os.rename(old_recipe,new_recipe);moved_recipe=True
            atomic_json(new_recipe,{**recipe,'output':destination.name})
    except Exception:
        if moved_recipe:
            os.rename(new_recipe,old_recipe);atomic_json(old_recipe,recipe)
        os.rename(destination,path)
        raise
    return destination
