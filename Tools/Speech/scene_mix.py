"""Concatenate a scene's line files into one listening mp3 (0.35 s between lines, each line loudness-matched)."""
import subprocess, sys, tempfile, os
def mix(files, out, gap=0.35):
    with tempfile.TemporaryDirectory() as d:
        parts = []
        for i, f in enumerate(files):
            p = os.path.join(d, f'{i:02d}.wav')
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', f, '-af', f'loudnorm=I=-19:TP=-1.5,apad=pad_dur={gap}', '-ar', '44100', '-ac', '1', p], check=True)
            parts.append(p)
        lst = os.path.join(d, 'l.txt'); open(lst, 'w').write(''.join(f"file '{p}'\n" for p in parts))
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-codec:a', 'libmp3lame', '-b:a', '128k', out], check=True)
if __name__ == '__main__':
    mix(sys.argv[2:], sys.argv[1])

def interleave(pairs, out, gap_in=0.5, gap_between=1.1):
    """[(english_file, gibberish_file), ...] -> one mp3: English line, short pause, gibberish line, longer pause, next"""
    files, gaps = [], []
    for e, g in pairs: files += [e, g]; gaps += [gap_in, gap_between]
    with tempfile.TemporaryDirectory() as d:
        parts = []
        for i, (f, gp) in enumerate(zip(files, gaps)):
            p = os.path.join(d, f'{i:03d}.wav')
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', f, '-af', f'loudnorm=I=-19:TP=-1.5,apad=pad_dur={gp}', '-ar', '44100', '-ac', '1', p], check=True)
            parts.append(p)
        lst = os.path.join(d, 'l.txt'); open(lst, 'w').write(''.join(f"file '{p}'\n" for p in parts))
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-codec:a', 'libmp3lame', '-b:a', '128k', out], check=True)
