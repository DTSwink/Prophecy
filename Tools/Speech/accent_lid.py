"""Spoken-language ID per clip / window with Whisper-small (sherpa-onnx int8 export): which language does the
pronunciation sound like? Used to spot lines where the voice drifts from a French accent (e.g. to Italian).
usage: python lid.py <audio files...> [--win 3.0]"""
import os, sys, subprocess, numpy as np, onnxruntime as ort, librosa
M = os.environ.get('LID_MODEL_DIR', '/tmp/claude-0/-home-claude/0fe64c57-808d-5039-ab94-85f914c99794/scratchpad/lid/m/sherpa-onnx-whisper-small/')
enc = ort.InferenceSession(M + 'small-encoder.int8.onnx', providers=['CPUExecutionProvider'])
dec = ort.InferenceSession(M + 'small-decoder.int8.onnx', providers=['CPUExecutionProvider'])
meta = enc.get_modelmeta().custom_metadata_map
codes = meta['all_language_codes'].split(','); toks = [int(x) for x in meta['all_language_tokens'].split(',')]
SOT = int(meta['sot']); FILT = librosa.filters.mel(sr=16000, n_fft=400, n_mels=80)
def load(p):
    raw = subprocess.run(['ffmpeg', '-v', 'quiet', '-i', p, '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32)
def mel(x):
    x = np.pad(x, (0, max(0, 480000 - len(x))))[:480000]
    S = np.abs(librosa.stft(x, n_fft=400, hop_length=160, window='hann', center=True))[:, :-1] ** 2
    L = np.log10(np.maximum(FILT @ S, 1e-10)); L = np.maximum(L, L.max() - 8.0); return ((L + 4.0) / 4.0).astype(np.float32)
def lid(x):
    k, v = enc.run(None, {'mel': mel(x)[None]})
    ck = np.zeros((12, 1, 448, 768), np.float32)
    logits = dec.run(None, {'tokens': np.array([[SOT]], np.int64), 'in_n_layer_self_k_cache': ck, 'in_n_layer_self_v_cache': ck.copy(),
                            'n_layer_cross_k': k, 'n_layer_cross_v': v, 'offset': np.array([0], np.int64)})[0][0, -1]
    l = logits[toks]; p = np.exp(l - l.max()); p /= p.sum(); return dict(zip(codes, p))
if __name__ == '__main__':
    args = sys.argv[1:]; win = None
    if '--win' in args: i = args.index('--win'); win = float(args[i + 1]); args = args[:i] + args[i + 2:]
    KEEP = ['fr', 'it', 'es', 'ca', 'pt', 'oc', 'ro', 'gl']
    for p in args:
        x = load(p); segs = [(0, len(x))]
        if win: n = int(win * 16000); segs = [(s, min(len(x), s + n)) for s in range(0, max(1, len(x) - n // 2), n // 2)]
        for a, b in segs:
            P = lid(x[a:b]); top = sorted(P.items(), key=lambda kv: -kv[1])[:3]
            print(p.split('/')[-1], f'{a/16000:5.1f}-{b/16000:5.1f}s', ' '.join(f'{c}:{P[c]:.2f}' for c in KEEP), '| top', ' '.join(f'{c}:{v:.2f}' for c, v in top), flush=True)
