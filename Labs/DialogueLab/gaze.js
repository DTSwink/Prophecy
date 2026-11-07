// Live gaze plan: WHAT each character looks at and WHEN over the dialogue, per scenario (standing / sit / walk).
// The angles are computed live from the actual positions every frame (app.js), so any layout works without baking.
// Research rules (Nov 6): speakers start a turn looking away and come back ~0.7 s in, are on the partner for the end of
// the turn, may look away at phrase ends; listeners mostly watch the speaker. Walking side by side: mostly the path
// (~15 % on the partner), glances at phrase / turn ends.
// User notes (Nov 6 evening): nobody holds a turned neck the whole time -> relief periods (head back to neutral, eyes
// forward or still on the partner from the corner of the eye); intermediate looks, not only "neutral" or "dead on";
// after looking away, don't snap straight back; walking: partner -> neutral first, look-arounds only later.
//
// fixation kinds:  partner     eyes + head on the partner's eyes
//                  soft        eyes on the partner, head mostly relaxed (hf = head-follow scale)
//                  between     direction b of the way from the neutral direction to the partner (head + eyes)
//                  rest        neutral: straight ahead from the body, slightly down (+ small offsets)
//                  avert       partner direction turned by (yaw, pitch)      (thinking / holding the floor)
//                  path, scan  walking: the way ahead / a look around (yaw, pitch from the path)
function rng(seed) { let s = seed >>> 0; return () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const lerp = (a, b, u) => a + (b - a) * u;

export function planGaze(script, kind, T, opts = {}) {
  const relief = opts.relief ?? true;   // neck breaks (rest / soft / between) on or off
  const out = {};
  const ids = opts.ids || ['S1', 'S2'], bys = ids.filter((x) => x[0] === 'B');
  // no neck break on short lines: up to 0.98 x the length of the Customer's (S2) last line (user, Nov 7)
  const lastS2 = [...script.lines].reverse().find((L) => L.spk === 'S2'), minBreakDur = lastS2 ? lastS2.dur * 0.98 : 2;
  for (const id of ids) {
    const r = rng(({ S1: 1301, S2: 7717, B3: 4243, B4: 9967 }[id] || 77) + (kind === 'walk' ? 50 : kind === 'sit' ? 90 : 0));
    const sgn = () => (r() < 0.5 ? -1 : 1);
    const ev = [];   // overlay events: highest prio wins, then the latest start
    const add = (t0, t1, k, o = {}, prio = 1) => { if (t1 > t0 + 0.05) ev.push({ t0, t1, kind: k, yaw: 0, pitch: 0, b: 1, hf: 1, ...o, prio }); };
    const mine = script.lines.filter((L) => L.spk === id), theirs = script.lines.filter((L) => L.spk !== id);
    const pEndsOf = (L) => (L.phraseEnds || []).map((p) => L.start + p[0]).filter((t) => t < L.start + L.dur - 0.3);

    if (kind !== 'walk') {
      // 1) base attention track: partner blocks alternating with relief (rest / soft / between)
      let t = 0, att = r() * 2;
      while (t < T) {
        const speaking = mine.some((L) => t >= L.start - 0.3 && t < L.start + L.dur);
        if (false) {   // neck breaks moved to the speaker's lines (below)
          const u = r(), d = lerp(1.6, 3.6, r());
          if (u < 0.4) add(t, t + d, 'rest', { yaw: sgn() * lerp(0, 8, r()), pitch: -lerp(3, 10, r()) });
          else if (u < 0.75) add(t, t + d, 'soft', { hf: lerp(0.15, 0.4, r()) });
          else add(t, t + d, 'between', { b: lerp(0.35, 0.7, r()) });
          t += d; att = 0;
        } else {
          const d = speaking ? lerp(1.5, 3.5, r()) : lerp(2.5, 5.5, r());
          add(t, t + d, 'partner'); t += d; att += d;
        }
      }
      // 2) conversation events on top
      for (const L of mine) {          // speaking
        const end = L.start + L.dur;
        // neck break (user, Nov 7): only the speaker, only inside 25-75 % of his line (back to normal before the end),
        // on some lines, at random; nothing for listeners
        if (relief && L.dur > minBreakDur && r() < 0.35) {   // 0.5 x 0.70 (user, Nov 7)
          const a = L.start + L.dur * lerp(0.25, 0.45, r()), b = Math.min(a + lerp(1.2, 2.6, r()), L.start + L.dur * 0.75), u = r();
          if (b - a > 0.8) {
            if (u < 0.4) add(a, b, 'rest', { yaw: sgn() * lerp(0, 8, r()), pitch: -lerp(3, 10, r()) }, 2);
            else if (u < 0.75) add(a, b, 'soft', { hf: lerp(0.15, 0.4, r()) }, 2);
            else add(a, b, 'between', { b: lerp(0.35, 0.7, r()) }, 2);
          }
        }
        if (r() < 0.75) add(L.start - 0.25, L.start + lerp(0.7, 1.2, r()), 'avert', { yaw: sgn() * lerp(10, 20, r()), pitch: r() < 0.55 ? -lerp(4, 10, r()) : lerp(2, 8, r()) }, 2);
        for (const pe of pEndsOf(L)) if (pe < end - 1.6 && r() < 0.3) add(pe + 0.05, pe + lerp(0.8, 1.4, r()), 'avert', { yaw: sgn() * lerp(8, 15, r()), pitch: -lerp(3, 8, r()) }, 2);
        add(end - 1.0, end + 0.3, 'partner', {}, 3);   // turn end: on the partner
      }
      for (const L of theirs) {        // listening: short glances down / aside, held long enough
        const end = L.start + L.dur; let t2 = L.start + lerp(1.0, 2.5, r());
        while (t2 < end - 1.2) { if (r() < 0.45) add(t2, t2 + lerp(0.7, 1.2, r()), 'avert', { yaw: sgn() * lerp(5, 12, r()), pitch: -lerp(5, 12, r()) }, 2); t2 += lerp(4, 7, r()); }
        if (r() < 0.6) add(L.start + 0.1, L.start + lerp(0.8, 1.4, r()), 'partner', {}, 3);   // a new speaker draws the eyes
      }
      if (kind === 'group') {
        // Group (research: Vertegaal et al. CHI 2001, 4-person talk: listeners look ~7x more at the speaker than at
        // others, speakers ~3x more at their addressee but give every listener glances; Holler & Kendrick 2015:
        // unaddressed listeners move their eyes to the next speaker ~0.25 s BEFORE the turn ends, in ~3/4 of cases)
        const pick = (arr) => arr[Math.floor(r() * arr.length)];
        if (id[0] === 'S') {
          for (const L of mine) for (const pe of pEndsOf(L)) if (bys.length && pe < L.start + L.dur - 1.2 && r() < 0.45)
            add(pe - 0.1, pe + lerp(0.8, 1.6, r()), 'partner', { who: pick(bys) }, 2);   // include the bystanders
          for (const L of theirs) { let t2 = L.start + lerp(1.5, 3, r());
            while (t2 < L.start + L.dur - 1) { if (bys.length && r() < 0.18) add(t2, t2 + lerp(0.6, 1.0, r()), 'partner', { who: pick(bys) }, 2); t2 += lerp(5, 8, r()); } }
        } else {
          const lines = script.lines;
          for (let i = 0; i < lines.length - 1; i++) {   // anticipate the next speaker
            const L = lines[i], N = lines[i + 1]; if (N.spk === L.spk) continue;
            const end = L.start + L.dur, early = r() < 0.75;
            add(early ? end - lerp(0.25, 0.6, r()) : end + 0.15, N.start + lerp(0.8, 1.3, r()), 'partner', { who: N.spk }, 3);
          }
          for (const L of lines) { let t2 = L.start + lerp(1.5, 3, r());   // look at another listener now and then
            while (t2 < L.start + L.dur - 1.2) {
              const others = ids.filter((x) => x !== id && x !== L.spk);
              if (others.length && r() < 0.35) add(t2, t2 + lerp(0.6, 1.2, r()), 'partner', { who: pick(others) }, 2);
              t2 += lerp(5, 8, r()); } }
        }
      }
    } else {
      // walking: glance windows (merged so there is no double look), then neutral, look-arounds only in clear gaps
      const g = [];
      for (const L of mine) {
        const end = L.start + L.dur;
        if (r() < 0.35) g.push([L.start + 0.2, L.start + lerp(1.0, 1.5, r())]);
        for (const pe of pEndsOf(L)) if (r() < 0.45) g.push([pe - 0.4, pe + lerp(0.5, 1.0, r())]);
        if (r() < 0.75) g.push([end - 0.6, end + lerp(0.4, 0.9, r())]);
      }
      for (const L of theirs) {
        if (r() < 0.5) g.push([L.start + 0.3, L.start + lerp(1.3, 2.0, r())]);
        if (r() < 0.3) { const a = L.start + L.dur * lerp(0.4, 0.7, r()); g.push([a, a + lerp(0.8, 1.3, r())]); }
      }
      g.sort((a, b) => a[0] - b[0]);
      const merged = [];
      for (const w of g) { const last = merged[merged.length - 1]; if (last && w[0] < last[1] + 2.0) last[1] = Math.max(last[1], w[1]); else merged.push([...w]); }
      for (const [a, b] of merged) {
        const u = r(), o = u < 0.55 ? {} : u < 0.8 ? { hf: lerp(0.25, 0.5, r()) } : { b: lerp(0.45, 0.7, r()) };
        const k = u < 0.55 ? 'partner' : u < 0.8 ? 'soft' : 'between';
        add(a, Math.min(b, a + 2.6), k, o, 3);
      }
      // look-arounds: never within 1.6 s after a glance or 1 s before the next one
      let t = lerp(2, 4, r());
      while (t < T) {
        const d = lerp(0.9, 1.6, r());
        const clear = merged.every(([a, b]) => t > b + 1.6 || t + d < a - 1.0);
        if (clear && r() < 0.55) {
          const u = r();
          if (u < 0.7) add(t, t + d, 'scan', { yaw: sgn() * lerp(15, 35, r()), pitch: -lerp(0, 10, r()) }, 1);
          else add(t, t + d, 'scan', { yaw: sgn() * lerp(0, 8, r()), pitch: -lerp(15, 25, r()) }, 1);   // a look at the ground ahead
          t += d + lerp(3, 6, r());
        } else t += 0.5;
      }
    }
    // no flicker: overlay looks of the same kind closer than 1.2 s merge; any overlay gap < 0.6 s is bridged
    const ov = ev.filter((e) => e.prio >= 2).sort((a, b) => a.t0 - b.t0);
    for (let i = 1; i < ov.length; i++) {
      const a = ov[i - 1], b = ov[i], gap = b.t0 - a.t1;
      if (a.kind === 'rest' || a.kind === 'soft' || a.kind === 'between') continue;   // a neck break never stretches past its end
      if (gap > 0 && ((a.kind === b.kind && gap < 1.2) || gap < 0.6)) a.t1 = b.t0 + (a.kind === b.kind ? Math.min(b.t1 - b.t0, 0.3) : 0);
    }
    // fixational micro-saccades: tiny shifts every 0.6-1.4 s (deg)
    const micro = []; let tm = 0; while (tm < T + 2) { micro.push([tm, (r() - 0.5) * 0.9, (r() - 0.5) * 0.6]); tm += lerp(0.6, 1.4, r()); }
    out[id] = { ev: ev.sort((a, b) => a.t0 - b.t0), micro, base: kind === 'walk' ? 'path' : 'partner' };
    out[id].seg = clean(out[id], T);
  }
  return out;
}

// resolve the overlapping events into one sequence of looks, then clean it: no look shorter than 0.7 s, and no
// "shaking no" between people: a short look at someone else (< 1.6 s) between two looks at the same person is dropped
// (user, Nov 7: the group speaker swung bystander -> listener -> bystander at the end of his line)
function resolve(P, t) {
  let best = null;
  for (const e of P.ev) { if (e.t0 > t) break; if (t < e.t1 && (!best || e.prio > best.prio || (e.prio === best.prio && e.t0 >= best.t0))) best = e; }
  return best || { kind: P.base, yaw: 0, pitch: 0, b: 1, hf: 1, who: null };
}
function clean(P, T) {
  const key = (e) => [e.kind, e.who || '', Math.round(e.yaw || 0), Math.round(e.pitch || 0), e.b, e.hf].join('|');
  let segs = [];
  for (let t = -0.5; t < T + 1; t += 0.05) {
    const e = resolve(P, t), k = key(e), last = segs[segs.length - 1];
    if (last && last.k === k) last.t1 = t + 0.05; else segs.push({ k, e, t0: t, t1: t + 0.05 });
  }
  const person = (s) => s.e.kind === 'partner' || s.e.kind === 'soft';
  for (let pass = 0; pass < 3; pass++) {
    const out = []; let carry = null;
    const isBreak = (x) => x.e.kind === 'rest' || x.e.kind === 'soft' || x.e.kind === 'between';
    for (const s of segs) {
      const last = out[out.length - 1];
      if (last && last.k === s.k) { last.t1 = s.t1; continue; }
      if (last && s.t1 - s.t0 < 0.7 && out.length > 1) {   // too short: keep the previous look...
        if (isBreak(last)) { if (carry === null) carry = s.t0; continue; }   // ...except a neck break, which must end on time: the next look takes it
        last.t1 = s.t1; continue;
      }
      out.push({ ...s, t0: carry ?? s.t0 }); carry = null;
    }
    for (let i = 1; i < out.length - 1; i++) {
      const a = out[i - 1], b = out[i], c = out[i + 1];
      if (a.k === c.k && person(a) && person(b) && (b.e.who || '') !== (a.e.who || '') && b.t1 - b.t0 < 1.6) { b.k = a.k; b.e = a.e; }
    }
    segs = out;
  }
  return segs.map((s) => ({ t0: s.t0, t1: s.t1, e: s.e }));
}

// what a character looks at, at time t
export function gazeAt(P, t) {
  if (P.seg) {
    let s = P.seg[0]; for (const x of P.seg) { if (x.t0 > t) break; s = x; }
    let m = P.micro[0]; for (const x of P.micro) { if (x[0] > t) break; m = x; }
    const e = s.e;
    return { kind: e.kind, who: e.who || null, yaw: e.yaw || 0, pitch: e.pitch || 0, b: e.b ?? 1, hf: e.hf ?? 1, t0: s.t0, my: m ? m[1] : 0, mp: m ? m[2] : 0 };
  }
  let best = null;
  for (const e of P.ev) { if (e.t0 > t) break; if (t < e.t1 && (!best || e.prio > best.prio || (e.prio === best.prio && e.t0 >= best.t0))) best = e; }
  let m = P.micro[0]; for (const x of P.micro) { if (x[0] > t) break; m = x; }
  const e = best || { kind: P.base, yaw: 0, pitch: 0, b: 1, hf: 1 };
  return { kind: e.kind, who: e.who || null, yaw: e.yaw, pitch: e.pitch, b: e.b, hf: e.hf, t0: best ? best.t0 : -1e9, my: m ? m[1] : 0, mp: m ? m[2] : 0 };
}
