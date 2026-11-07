// Speech -> pose motions: places the user's saved pose profiles on the dialogue timeline.
// One gesture per phrase (most phrases), the pose reaching its apex on the phrase's stressed word (the most prominent
// pitch accent early in the phrase), the pose chosen from the script emotion at that moment, the profile's ranges
// sampled with one coherent variation value u. Deterministic (seeded per character), speaker only.
const AROUSAL = { HAPPY: 0.6, WARM: 0.35, SKEPTIC: 0.35, SURPRISE: 0.75, OFFENDED: 0.8, EXASPERATED: 0.65, SMUG: 0.3, THINK: 0.15, INDIGNANT: 0.85 };
function rng(seed) { let s = seed >>> 0; return () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const pick = (r, items) => { const tot = items.reduce((a, [, w]) => a + w, 0); if (tot <= 0) return null; let x = r() * tot; for (const [k, w] of items) { x -= w; if (x <= 0) return k; } return items[items.length - 1][0]; };

// how well each kind of pose fits a mood (explanatory/emphasis poses = 'explain')
const FIT = {
  shrug: { EXASPERATED: 3, SURPRISE: 1.5, SKEPTIC: 1.2, INDIGNANT: 1, _: 0.25 },
  plead: { EXASPERATED: 2.2, INDIGNANT: 1.2, OFFENDED: 0.8, WARM: 0.4, _: 0.15 },
  explain: { HAPPY: 1.5, WARM: 1.4, OFFENDED: 1.5, INDIGNANT: 1.3, SKEPTIC: 1, SMUG: 0.6, THINK: 0.4, EXASPERATED: 0.6, _: 1 },
};
const kindOf = (name) => /shrug/i.test(name) ? 'shrug' : /plead/i.test(name) ? 'plead' : 'explain';

const lengthOf = (P) => P.blendIn + Math.max(P.hold, -P.blendIn) + P.blendOut;

// arms[k] = 'L' | 'R' | 'both' for pose k (which arm the pose uses)
export function planSpeech(script, motions, poseNames, takeAt, arms, opts = {}) {
  const pFirst = opts.pFirst ?? 0.6, pOther = opts.pOther ?? 0.42, pChain = opts.pChain ?? 0.5;
  const events = [];
  const kindOfPose = (k) => kindOf(poseNames[k] || '');
  for (const id of ['S1', 'S2']) {
    const r = rng(id === 'S1' ? 4711 : 9091);
    const emos = script.emotions.filter((e) => e.char === id);
    const moodAt = (t) => { let best = '_', bw = 0.15;
      for (const e of emos) { const w = (t < e.on ? 0 : t < e.on + e.attack ? (t - e.on) / e.attack : t < e.off ? 1 : Math.max(0, 1 - (t - e.off) / 1.5)) * e.intensity; if (w > bw) { bw = w; best = e.preset; } }
      return best; };
    let lastPose = -1, busyUntil = -9;  // no new gesture while the previous one (or its chain) is still out
    for (const L of script.lines) {
      if (L.spk !== id) continue;
      const ends = new Set(L.phraseEnds.map((p) => p[0])); const phrases = []; let cur = [];
      for (const w of L.words) { cur.push(w); if (ends.has(w[2])) { phrases.push(cur); cur = []; } }
      if (cur.length) phrases.push(cur);
      const usedKinds = new Set();
      phrases.forEach((ph, i) => {
        const t0 = L.start + ph[0][1], t1 = L.start + ph[ph.length - 1][2];
        if (t1 - t0 < 0.5 || r() > (i === 0 ? pFirst : pOther)) return;  // about half as many as before (user)
        const mood = moodAt(t0 + 0.2);
        const options = [];
        for (const m of motions) {
          const kind = kindOfPose(m.pose);
          if ((kind === 'shrug' || kind === 'plead') && usedKinds.has(kind)) continue;
          let w = FIT[kind][mood] ?? FIT[kind]._;
          if (m.pose === lastPose) w *= 0.2;
          options.push([m, w / motions.filter((x) => x.pose === m.pose).length]);  // several profiles of one pose share its weight
        }
        const m = pick(r, options); if (!m) return;
        // apex on the stressed word: most prominent word in the first 60% of the phrase (stress ~early in the word)
        const head = ph.slice(0, Math.max(1, Math.ceil(ph.length * 0.6)));
        const w = head.reduce((a, b) => (b[3] > a[3] ? b : a));
        const apex = L.start + w[1] + 0.35 * (w[2] - w[1]);
        const u = r(); const P = takeAt({ pose: m.pose, r: m.ranges }, u);
        const start = Math.max(apex - P.blendIn, L.start - 0.6);
        if (start < busyUntil) return;
        let ev = { char: id, line: L.id, start, apex, P, u, motionId: m.id, motionName: m.name, pose: m.pose, mood, chain: 0 };
        events.push(ev); lastPose = m.pose; usedKinds.add(kindOfPose(m.pose));
        // an explanatory pose may flow straight into another explanatory pose of the SAME arm (50%) instead of
        // blending back: the next pose starts where this one would start leaving, this one stays fully on until the
        // next has arrived (so the arm goes pose -> pose, never through the idle)
        while (kindOfPose(ev.pose) === 'explain' && ev.chain < 3 && r() < pChain) {
          const arm = arms[ev.pose];
          const cands = motions.filter((x) => x.pose !== ev.pose && kindOfPose(x.pose) === 'explain' && arms[x.pose] === arm);
          if (!cands.length) break;
          const n = cands[Math.floor(r() * cands.length)];
          const u2 = r(); const P2 = takeAt({ pose: n.pose, r: n.ranges }, u2);
          const s2 = ev.start + ev.P.blendIn + Math.max(ev.P.hold, 0.15);
          if (s2 > L.start + L.dur + 0.3) break;   // don't keep gesturing after the line
          const apex2 = s2 + P2.blendIn;
          // stays on until the next has arrived, then fades out (0.35 s): with a strength < 1 the next pose doesn't fully
          // cover it, so an instant drop showed as a hand hitch (user, Nov 6)
          ev.P = { ...ev.P, hold: apex2 - ev.start - ev.P.blendIn, blendOut: 0.35, outEaseIn: 0.5, outEaseOut: 0.5 };
          ev.chainedTo = n.name;
          ev = { char: id, line: L.id, start: s2, apex: apex2, P: P2, u: u2, motionId: n.id, motionName: n.name, pose: n.pose, mood, chain: ev.chain + 1 };
          events.push(ev); lastPose = n.pose;
        }
        busyUntil = ev.start + lengthOf(ev.P) - 0.2;
      });
    }
  }
  return events.sort((a, b) => a.start - b.start);
}
