"""Cut the French opener ("Bon, alors.") off primed takes using ElevenLabs character timestamps."""
import json, subprocess
def cut_point(al, prime):
    cs, st, en = al['characters'], al['character_start_times_seconds'], al['character_end_times_seconds']
    text = ''.join(cs); assert text.startswith(prime), text[:30]
    k = len(prime) - 1
    nxt = next(i for i in range(k + 1, len(cs)) if not cs[i].isspace())
    a, b = en[k], st[nxt]
    return max(a + 0.02, a + 0.5 * (b - a))
def trim(mp3_in, json_in, prime, out):
    al = json.load(open(json_in))['alignment']; t = cut_point(al, prime)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', f'{t:.3f}', '-i', mp3_in, '-af', 'afade=t=in:d=0.015', '-ar', '44100', out], check=True)
    return t
