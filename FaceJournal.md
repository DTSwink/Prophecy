# Face journal

Separate handoff for facial expressions: baked face morph targets, wrinkle textures, face material
and curve/runtime hookup. Unreal-wide rules (golden rules, build/restart, preserve user Play/BP) still
come from ProjectJournal.md. Technical reference: [Docs/FaceExpressions.md](Docs/FaceExpressions.md).

**Goal (user, Nov 4):** facial expressions at the lowest possible framerate cost. Everything pre-computed,
no procedural face. Characters are MetaHuman meshes retargeted to the UEFN skeleton with NO face rig,
NO DNA/RigLogic. Chosen approach: baked morph targets driven by curves + optional wrinkle (and later
flush) textures in the face material. Not bones (keeps the shared 78-bone UEFN skeleton untouched,
keeps the cost on the GPU while NN/Jolt load the CPU). UE 5.7.4 now, 5.9 later (morphs/curves are stable API).
Caveat for later: Nanite skinned meshes still don't support morphs (Epic, Aug 2026).

## Current status

**November 4 (later) — skin colour added to the wrinkle package (cloud), NOT imported.** Pushed commit
c890dee7 (05:47) predates this: `T_Face_WrinkleMasks_3.png` changed and `T_Face_FlushRegion.png` is new.
- Local blood (Ada cm1-3): stretch blanches, bunching reddens. 95-97% of the colour change lies on one red
  direction, so it is stored as a signed RELATIVE scalar per layer in the spare B/A of WrinkleMasks_3
  (256 keeps 91-96% of the energy). Zero extra texture reads. Same weights as wrinkles (cm == wm in DNA).
- Whole-face flush: `T_Face_FlushRegion` 128 (smoothed skin redness of Ada's map: nose, cheeks, lips,
  forehead; ~0 on the neck) * auto amount saturate(.6 Effort + .8 Shout + .6 Anger + .35 Pain + FlushExtra)
  * FlushStrength. 1 extra read of a 128 texture, only while flushed. Per-pixel redness was rejected (blotchy).
- Pallor: desaturates/cools up to 35% (first try 55% looked like plaster). ALU only. **Time-based (user:
  must not snap):** gameplay sets `DeathTime` = World->GetTimeSeconds() ONCE at death (default -1 = alive,
  reset to -1 on revive); the material eases in with smoothstep over `PaleDuration` (default 8 s) using the
  Time node (game time, pause/dilation aware). Independent of the Dead morph curve; no per-tick CPU work.
  Set params with SetScalarParameterValueOnMaterials so head + body stay in sync. Fade strip: `pallor_fade.png`.
- Flush still follows the expression weights (fades in/out with the expression curves). If it should
  linger after an expression ends, bake a slower release into the expression curves via `FlushExtra`.
- Collar audit at the Boss's 46 head/body seam vertices: wrinkle masks <=1.2%, detail ~0, blood neutral
  (|v-0.5| 0.002), flush region faded to exactly 0 within the collar band. **Pallor is whole-head by
  design: the body material needs `FacePallorBody.hlsl` (same params), or death shows a neck line.**
- `FaceWrinkles.hlsl` now has Additional Output `OutColor` (BaseColor in, adjusted colour out).
  Preview `colour_preview.png` (Ada colour stand-in; body mesh flat in the preview).

**November 4 — wrinkle textures built (cloud), NOT imported.** Source: Epic's public MetaHuman DNA
Calibration repo, Ada's wm1/wm2/wm3 wrinkle normal maps and 37 region masks (shared MetaHuman UVs, so
they fit the Boss head exactly). Per-expression mask weights come from Ada.dna's animated-map logic for
the same control values as the morphs. Detail = wrinkle map minus Ada base normal in slope space, so no
Ada pores/identity are carried. Two layers: stretch (wm1+wm3, merge loses ~3% of detail energy) and
compress (wm2); a single merged layer would lose ~27%, so it was rejected.
- `Exports/FaceWrinkles/T_Face_WrinkleDetail.png` 1024 RGBA (RG stretch XY, BA compress XY, DX green).
- `T_Face_WrinkleMasks_0..3.png` 256 RGBA, 14 (expression, layer) channels; table in `wrinkle_layout.json`.
- `FaceWrinkles.hlsl`: Custom-node code. Neutral face = uniform branch, zero texture reads; expressive =
  5 reads + ~30 ALU. Dead and LookDown reuse the blink channels (no extra textures). Look* have no wrinkles.
- Import: `Tools/FaceExpressions/import_face_wrinkle_textures.py` -> `/Game/_mygame/MetaHumans/FaceWrinkles`,
  sRGB off, Detail BC7, masks TC_Masks, not saved.
- Verified: the snippet math in numpy against shipped textures matches the preview normals within 8-bit
  rounding (mean 0.05 deg, p99 0.3 deg). Offline Cycles preview `wrinkles_preview.png` uses Ada's colour/
  normal maps as stand-ins (Boss textures are only in .uasset): NOT an in-engine look check.
- Not done: wiring into the head material. Boss head uses `MI_Face_Skin_Baked_LOD3_VT` (parent shared
  with other heads, already has Boss-only static switches). Plan: add a default-off static switch
  "Use Face Wrinkles" to that parent, Custom node between the existing tangent normal and the Normal pin.
  Needs user OK before touching the shared material.

**November 4 — Boss expression morphs built (cloud), NOT imported.**
14 morphs: Blink_L, Blink_R, JawOpen, Effort, Pain, Shout, Anger, Fear, Grin, Dead, LookLeft/Right/Up/Down.
- FBX: `Saved/BossUEFNCompatible/20261104_Expressions/SKM_Boss_UEFN_Fitted_Expressions.fbx`, built from
  the 20260908_Stitched keeper FBX with shape keys added only. Round trip: bones max 6.9e-6, vertices
  8.7e-8 m, UV/weights/materials/vertex order identical, normals within 4.3e-4.
- Import: `Tools/MetaHuman/import_boss_expressions.py` (no Play; backup; asserts reference rig + base
  vertices unchanged and 14 morphs; does NOT save).
- Method: numpy RigLogic on Ada.dna (head at LOD0 incl. blendshapes, sampled to LOD3; other parts LOD3
  rig), UV correspondence (Boss head = MetaHuman LOD3 parts 1:1), similarity transfer (scale 1.004).
  Limit: Ada-proportioned motion transferred to his face, not his own DNA.

## Next

1. User/agent in editor: run both import scripts, look at morphs + textures, save.
2. With user OK: material switch + Custom node; same-named curves flagged Morph + Material.
3. Runtime: curve-only expression sequences (or native SetMorphTarget/SetScalarParameter per tick) on
   hit/attack/death/idle blink. Morphs LOD0 only for the Boss (single LOD).
4. Colour (blood/flush/time-based pallor) built. Body material needs FacePallorBody.hlsl.
   **User rule (Nov 4): push and Unreal wiring/imports only when the user says so.**
5. Other characters: export their MetaHuman-LOD3 face/character FBX; rerun `Tools/FaceExpressions` (~1 min).
   Wrinkle textures are shared as-is (same UVs).

## Reproduce (cloud)

`Tools/FaceExpressions/`: rl.py (RigLogic), match*.py/align.py (correspondence), bake.py (morph deltas),
export_boss.py + verify_rt.py (FBX), wr_build.py (wrinkle textures), wr_render.py/apply_render.py (previews).
Needs Python 3.10 + Epic MetaHuman-DNA-Calibration (Maya2024 linux bindings, Ada.dna, data/maps, data/masks)
and Blender 5.2 `bpy` (pip). All paths in the scripts are cloud paths.

## Speech (started November 4)

Goal: endless believable gibberish chatter with matching mouth + expression, near-zero frame cost.
Decision (user): pre-record WHOLE lines with ElevenLabs (not stitched words); bake a full face performance per
line offline (visemes from the known text + API character timing, jaw from loudness, brow emphasis, blinks,
mood expression). Runtime = one audio clip + one curve track per speaker, random no-repeat line picking,
cap ~3-4 audible speakers.
- The cloud session cannot reach api.elevenlabs.io (network policy 403), so generation runs on the laptop.
- `Tools/Speech/elevenlabs_probe.py` (stdlib, key only from env `ELEVENLABS_API_KEY`, never printed) +
  `Tools/Speech/QUESTIONS_FOR_CODEX.md`; Codex answers in `Tools/Speech/ANSWERS.md`, probe output in
  `Saved/Speech/probe/` (git-ignored).
- Nov 4 probe (Codex): key OK, all 4 test calls 200 with character alignment (v2, v3, v3+[angry], flash 2.5).
  Starter tier, ~36.5k chars left this cycle (reset ~Nov 21-22). Models include eleven_v4 / v4_turbo.
  User: voices = I propose candidates; budget later; emotions come from real multi-speaker dialogue; battle
  shouts are a separate system. Commercial use confirmed by user.
- Nov 4 language v1 (seed 7): `Tools/Speech/lang.py` + `LANGUAGE.md` (research-based French-flavoured design,
  real-word filter, sound-span spelling for visemes, relexification of English scenes). Mockup scene
  `Tools/Speech/batches/mockup1_gate.json` (3 speakers: Adam/Callum/Lily premade voices, 12 lines, tags),
  variants eleven_v3 vs eleven_v4 with language_code fr, ~1,390 chars total. Runner `Tools/Speech/el_generate.py`
  (stdlib, with-timestamps then plain fallback, writes Saved/Speech/<batch>/index.html listening page).
  Waiting for the laptop run + user listening verdict.
- **Automation (Nov 4): no Codex needed.** The cloud session drops `speechNNN_*.ps1` jobs into the existing
  `Saved/ClaudeJobs/inbox` (user-run `runner.ps1`, heartbeat in `heartbeat.txt`); output in `outbox/<job>.log` +
  `.done`. Jobs only call `Tools/Speech/el_generate.py` (key from the Windows user env, never printed). The cloud
  environment itself cannot reach ElevenLabs (a network secret added to the claude.ai/code Default environment
  did not apply to this app's built-in environment).
- speech001_mockup1: 24/24 lines HTTP 200 with character alignment (eleven_v3 and eleven_v4, language fr); text
  matches alignment, timestamps monotonic; non-verbal tags produce real sounds (sigh +0.5-0.9 s, nervous laugh
  +1.2-1.5 s before speech). ~54 s (v3) / 50 s (v4) of dialogue. Account reported 188 credits used (counter may
  lag), 36,386 left. Listening page: `Saved/Speech/mockup1_gate/index.html`. Awaiting user verdict.
- **Overnight Nov 4: speech corpus v1** (user asleep; brief: varied 2-4 way scenes, small talk / storytelling /
  disputes / bargaining, contextual tags watered down for casual talk, translated with a real grammar).
  Pool 8,228 scenes / 71,905 lines (MELD, Friends transcripts, CRD3 Critical Role, Deal or No Deal, 25 original
  Prophecy scenes). 81% of lines untagged; intensity capped per category (shouts only in disputes). Grammar layer
  `Tools/Speech/lang2.py` (lemma roots, endings, French adjective order, zou...teu negation, elision, consistent
  names); lexicon `Tools/Speech/lexicon_v2.json.gz` = the language's memory, keep it. Starter bank
  `Tools/Speech/corpus/starter_bank_v1.json`: 81 scenes / 635 lines / ~30.8k chars (~34 min). Details:
  `Tools/Speech/corpus/CORPUS.md`, preview `PREVIEW.md`. Full pool (~4.2M chars) in `Saved/Speech/corpus/`.
  Nothing generated with ElevenLabs overnight (budget is the user's call).
- **Nov 4 A/B (apple haggling scene, PREVIEW scene 1):** English vs v2 gibberish, same voices (George/Jessica, eleven_v3).
  User verdict: the gibberish "loses all the color", and the accent drifts (some words French, some Spanish-like with a
  rolled r). Measured: gibberish 51.8 s vs English 38.0 s, melody correlation with the English ~0.3.
- **Fix (Nov 4, user: "yes do it"):**
  - `Tools/Speech/lang3.py` (language v3, on top of lang2): French-looking spelling with the same sounds (no final
    -a/-o/-u, -are/-ore/-ère/-ure, quon/quez(qu')/cou/joux/jus/miot/liat, -mant adverbs), French silent plural -s
    instead of the audible -i, root syllables = English word syllables (CMU dict), and `translate_aligned()` returns
    the English source word of each gibberish word. Memory: `Tools/Speech/lexicon_v3.json.gz` (v2 roots kept where
    the syllable count already matched). Corpus NOT rebuilt with v3 yet (wait for the user's verdict).
  - Native French library voices added to the account (2 of 10 slots): Marcel_FR (kENkNtk0xyzG09WW40xE, warm male)
    and Sarah_FR (t8BrjWUT5Z23DLLBzbuY, "expressive, ideal for v3"). Library list: `Saved/Speech/voices/fr_library.json`.
  - `Tools/Speech/prosody.py` (cloud, Praat/parselmouth): English performance -> gibberish line. Word-start anchors
    from both alignments, PSOLA time warp (0.6..1.6), English F0 in semitones re-centred on the gibberish voice,
    per-word stress gain. `el_tools.py sts` / `sts-batch` = ElevenLabs speech-to-speech cleanup pass (same voice).
  - Result on the apple scene: v3 base 36.1 s vs English 38.0 s (was 51.8 s); melody correlation with the English
    0.29 (v3 base) -> 0.74 (curated). Files: `Saved/Speech/ab_apples_v3/` (v3_fr = base, curated_psola,
    curated_sts; melody correlation after the STS pass 0.62). Awaiting the user's listening verdict.
  - Cost (apple scene, ~36 s): TTS 525 chars; speech-to-speech ~460 credits per pass (two passes = 918, ~13 credits
    per second of audio), i.e. it roughly DOUBLES the cost of a line. Prosody transfer itself is free (cloud).
  - User (Nov 4, 18:12): full transfer is too altered (PSOLA artefacts carry into the voice-changer pass); voices
    sound low quality. Knobs added to `prosody.transfer`: melody (0..1 blend), timing (0..1), phrase_only (align
    pauses only), clamp, gain_db. Presets tried: light (0.5 / 0.6 / phrase / 0.8-1.25 / 3 dB) and medium
    (0.7 / 0.8 / phrase / 0.7-1.4 / 4 dB): melody correlation 0.72 / 0.81 (full was 0.74; big local warps hurt).
  - Voice quality: the library voices are Professional Voice Clones, which ElevenLabs says are not fully optimised
    for eleven_v3 yet. Tested the same text with eleven_v4 and eleven_multilingual_v2 (no tags) in
    `Saved/Speech/ab_apples_v3_v4` / `ab_apples_v3_ml2`. After the voice changer: light 0.60, medium 0.72
    melody correlation (full 0.62). Sent to user: apples_v3_light / _medium (with voice changer), _base_v4, _base_ml2.
    Awaiting verdict on preset + model.
- **Nov 4 evening, user decision path:** user preferred plain `ab_apples_v3_ml2` (eleven_multilingual_v2, no tags, no
  prosody transfer) on voice quality; the transferred ml2 version sounded robotic (PSOLA pitch rewrite) -> transfer
  shelved. User: don't change speed. Settings sweep `Saved/Speech/ab_apples_ml2_knobs/` (seed 4242, one knob per
  variant from A = stability .40 / similarity .75 / style .20): B stab .20, C stab .70, D style 0, E style .50,
  F sim .50, G sim .95. 1,265 credits used, 32,669 left. Awaiting the user's pick.
  User asked for combos 010, 110, 100, 111 (stability/similarity/style). First misread as low/high end of the sweep
  (`ab_apples_ml2_knobs2/`); user meant ABSOLUTE values 0.0/1.0 -> `Saved/Speech/ab_apples_ml2_knobs3/`.
  Next round (user): stability .25/.5/.75 at similarity 0 style 0, plus .25/0/1 -> `Saved/Speech/ab_apples_ml2_knobs4/`.
  Credits left 30,403.
- **Nov 4 ~20:00, intonation (user):** the gibberish isn't flat, its pitch movement just lands differently from the
  English (wrong words peak, statements end rising) -> uncanny. User asked Claude to self-check audio more.
  - `Tools/Speech/analyze.py` (cloud): melody vs English per word (word_corr, peak_match, end_match), damage (natural
    wobble micro_st, straight glides, jumps, HNR) and Microsoft DNSMOS P.835 quality (ONNX from GitHub DNS-Challenge),
    plus pitch plots. Calibrated on takes the user judged: DNSMOS overall ml2 base 3.28 (good) > v3 base 3.12 (low
    quality) = ml2 transfer 3.12 (robotic) > v3 full transfer 3.02 (altered); the robotic one lost ~28% of wobble.
    Praat PSOLA resynthesis alone (no change) costs 3.28 -> 3.22.
  - `Tools/Speech/nudge.py` (gentle melody nudge, replaces prosody.py's pitch rewrite): own pitch + slow delta from the
    English (word heights, peak word, sentence-end rise/fall), capped 3/5 st, no time change. On ml2 base: word_corr
    0.44 -> 0.85, end_match 0.44 -> 0.67, DNSMOS 3.21 (= resynthesis cost only), wobble kept. Stronger ending cap (8)
    was worse. Test harness `eval_nudge.py`.
  - Sent: `apples_EN_then_gib_base.mp3` / `_nudged.mp3` (each English line followed by its gibberish line).
- **Nov 4 ~20:15, Latin test (user idea: does v3 "understand" Latin and intone by meaning?).** Apple scene translated
  to classical Latin by Claude (`Tools/Speech/batches/ab_apples_latin.json`, with word maps to the English), voiced on
  eleven_v3 and eleven_v4 with the English take's voices (George/Jessica) and tags, no language_code (Latin is not an
  official language). Scores vs English: peak on the right word 46% (v3) / 54% (v4) vs 15% for the gibberish; sentence
  endings right 73% / 62% vs 44%; DNSMOS 3.31 / 3.20; but slower: 44.8 s / 41.4 s vs English 34.4 s. Sent
  `apples_latin_v3.mp3`, `apples_latin_v4.mp3` + `apples_en.mp3` as separate files. 30,054 credits left.
- **Nov 4 ~21:30, more real languages (user):** Occitan, Welsh, Esperanto translated by Claude
  (`batches/ab_apples_{occitan,welsh,esperanto}.json`), v3 + v4, English take voices, no language code.
  | take | peak | ending | DNSMOS | length (EN 34.4 s) |
  | latin v3/v4 | 46/54% | 73/62% | 3.31/3.20 | 44.8/41.4 |
  | occitan v3/v4 | 29/42% | 73/71% | 3.26/3.18 | 36.1/36.5 |
  | welsh v3/v4 | 27/25% | 46/60% | 3.26/3.04 | 48.2/42.8 |
  | esperanto v3/v4 | 33/23% | 56/44% | 3.24/3.17 | 42.6/43.0 |
  | gibberish ml2 | 15% | 44% | 3.28 | 30.7 |
  (peak metric is noisy across languages: sentence splits differ). Files `apples_<lang>_<v3|v4>.mp3`.
  User liked Occitan v4 but heard mixed French/Italian-ish accent -> Occitan v4 with language_code fr
  (`Saved/Speech/ab_apples_occitan_fr/v4_fr`, `apples_occitan_v4_fr.mp3`).
- **Nov 4 ~22:00, Occitan v4 with the FRENCH voices (Marcel_FR / Sarah_FR), user: French voices are a must.**
  Three takes, no language code: plain / `[French accent]` tag on every line / French opener "Bon, alors." spoken first
  and cut off with the character timestamps (`Tools/Speech/trim_prime.py`; all cuts land in silence, < -53 dB).
  | take | peak | ending | DNSMOS | length |
  | plain | 46% | 58% | 3.15 | 32.8 s |
  | [French accent] tag | 44% | 69% | 3.14 | 33.8 s |
  | French opener (cut) | 31% | 75% | 3.26 | 33.7 s |
  Files `occitan_FRvoices_1_plain / 2_accent_tag / 3_french_opener.mp3`. 28,007 credits left.
  analyze.words now drops multi-word tags like [French accent].
- **Nov 4 ~22:50, user decision:** speech mockup = Occitan, eleven_v4, French voices (Marcel_FR/Sarah_FR),
  `[French accent]` tag on every line (`Saved/Speech/ab_apples_occ_fv_tag/v4/`, `occitan_FRvoices_2_accent_tag.mp3`).
  Next: face work on that audio (lipsync + micro-expressions + subtler emotion blending), all offline.
  Plan: `Docs/FaceSpeechPlan.md` (full-rig RigLogic animation per frame offline -> compact morph basis + curves).
  espeak-ng has no Occitan -> rule-based Occitan G2P + ElevenLabs character timestamps.
- **Nov 5 ~05:00, better render (user: Blender on the laptop, not Unreal).** `Saved/SpeechMHA/blender/render_face.py`
  (Blender 5.1, laptop RTX 4060): Boss FBX + per-frame vertex deltas + MetaHuman animated wrinkle normals (wm1-3) and
  blood-flow colour maps (cm1-3) driven per frame by Ada.dna's animated-map table (`anim_mapweights.py`), 37 region
  masks packed 4/RGBA (Eevee sampler limit). Ada's skin maps are stand-ins (Boss textures only exist as .uasset).
  Speed lessons: Cycles denoised on the CPU by default (7.5 of 10 s/frame) -> OptiX denoiser; node value edits per
  frame are slow -> weights as object custom props read by Attribute nodes; Eevee ~0.6 s/frame is the default.
  Wrinkles were invisible under frontal soft light; a raking side light shows them at x1 (user: x1 + side light good).
- **Nov 5 ~06:00, listening + blinks (user).** Unreal's audio solve has no listener mode and gave ~1 blink in 34 s
  (Generate Blinks not set). `dialog_layer.py` (cloud) builds both characters' tracks over the scene: speaking =
  Unreal curves + head; listening = nods at phrase ends with low pitch (3-5 deg, single/double), authored reactions
  keyed to words by meaning (smile, brows, frown, tilt, head shake, thinking glance), delayed 30 % smile mimicry,
  idle drift; blinks near phrase ends / with gaze shifts / long blinks with nods (~28/min); gaze held on the partner
  with vestibulo-ocular compensation, speaker looks away at turn start; 0.4 s cross-fade at turn changes.
  `bake_dialog.py` -> PCA-compressed deltas (2.7 MB), `render_dialog.py` two heads, fixed camera, neck/head bones
  (30/30/40 %). Video `Boss_dialog_listening.mp4`. Line starts must use DECODED audio length (mp3 container duration
  adds ~0.04 s/line). Bridge gotcha: committing a changed file from the same staged path re-sent the old content ->
  always stage a new file name.
- **Nov 5 ~08:00-12:00, listener v2 = "inner voice" (user idea, user asleep, variants to pick).** User feedback on v1:
  head too strong (/4), snap at turn end (needs inertia), listener mouth too quick ("demented" smiles), nods all the same,
  listener robotic. Now: each listener gets an inner-voice track (ElevenLabs v4, own French voice, English murmurs placed
  on the speaker's words: `Saved/SpeechMHA/listen/listen_inner_{A,B}.json`, `assemble_inner.py`, ~1000 credits), solved
  by Unreal audio-to-face (`listen/mha_listen.py`, 1 solve per character per variant, ~22-26 min each at Idle priority);
  we keep only head + upper face (brows, eyes, cheeks, nose) for the listener, mouth/jaw are ours (closed + slow
  low-passed mood echo x0.45). All heads x0.25. Turn end: 2 s smootherstep from the held last speaking expression/head.
  Blinks/gaze/VOR ours. `dialog_layer2.py <A|B|C> <listen out dir>` -> `bake_dialog.py <tag>` -> `render_dialog.py`
  (FACE_NPZ=dialog_<tag>.npz). Variants: A murmurs ("mm", "heh"), B fuller inner monologue, C = B with Unreal mood
  Neutral. Videos Dialog_A_inner_murmurs / Dialog_B_inner_monologue / Dialog_C_monologue_neutral.mp4.
  Unreal "generate blinks" property not found via Python (blink props []). A watchdog timeout would have killed the
  last solve: stopped only the watchdog, Unreal finished and exited by itself, checked no leftovers.
- **Nov 5 ~17:00, user picked variant A; round 2 (`dialog_layer3.py`, tag A4, video Dialog_A_v2_emotions.mp4).**
  Head continuity: speaking pose extended through listening gaps by the exact last/first frame, listening weight up over
  1.6 s (smootherstep) after a turn and down over 0.8 s around the next, zero-phase smoothing (0.06 s x2) on the head.
  Listening head ~2x slower: zero-phase gaussian low-pass with sigma chosen for a 0.5 velocity ratio (~0.4 s), std kept.
  Emotion overlay from the script, word-anchored (EMO_W: char, line, first/last word, preset, intensity; presets HAPPY,
  WARM, SKEPTIC, SURPRISE, OFFENDED, EXASPERATED, SMUG, THINK, INDIGNANT on raw controls), timed on the speech: speaker
  leads words by 0.3 s, holds to the last word, releases 0.8-2 s into the pause (2.5 s at turn end); listener reacts
  0.4 s after hearing the word, 1 s rise, holds 0.6 s past, releases 1.5-3 s; 0.35 s zero-phase blend; soft-OR on the
  face (a+b-ab) so nothing saturates.
- **Nov 5 ~18:30, round 3 picked as "perfect" (tag A5, Dialog_A_v3_stronger_emotions.mp4):** EMO_GAIN 1.6 on every
  script emotion (capped per event), sad brows (EXASPERATED browRaiseIn 0.9, event intensity 1.0) on "every day I lose
  money" (~0.91 on screen).
- **Nov 5 ~19:15, backup (user asked):** the cloud-only pipeline scripts are now in `Tools/FaceSpeech/` (README.md has
  the run order; NOT committed, no push); final video with sound in `Saved/SpeechMHA/final/`. Derived data (ada_*.npz,
  corr/align, ~75 MB) is not copied: regenerable from Epic's DNA Calibration repo + Tools/FaceExpressions scripts.

## TEMP - village dialogue triggers to implement later (user, Nov 5 21:18)
Casual village talk that can escalate into real game events. Ideas kept for later:
- **Conflict, possible fight.** An argument that can tip into a real fight in the game.
- **Snitch to conflict, pointing to the victim.** Someone informs on another person; the conflict turns toward the one pointed out.
- **Begging for money.** A villager begs; the player gives money if the plea succeeds.
- **Questing for events:** concert, loup-garou (werewolf game), swim race, training, taking food and eating at the beach.
- **Multi-way discussion degenerating.** Some try to stop one person from hitting another. If he gets through, a fight
  starts. While restrained, he keeps playing his dialogue with an angry look.
(Story coverage gap noted the same day: only 2 scripts exist, apple seller = 2 speakers M+F and the gate = 3 speakers
2M+1F; no monologues, no M+M / F+F, no 3M / 1M+2F / 3F. New trigger scenes can fill these combinations.)

## Dialogue Lab (Nov 5)
- `Labs/DialogueLab/` (port 8842, local only, three.js r170 vendored: no internet). Start: `launch.ps1` (`-Stop` to stop), open http://127.0.0.1:8842/ in Claude's browser pane.
- Shows scene `apples_occitan_A5` (approved v3 face: Unreal speech + inner-voice listener + script emotions) on two Boss bodies in the game idle (all 87 bones, fingers incl.), audio synced at 1x.
- Layers: face morphs (PCA `mu`+`pc0..96`), wrinkles/skin colour (cm/wm maps + 37 region masks in one atlas), head motion (additive over neck_01/neck_02/head), body idle (off = bind A-pose). Cameras: two-shot, seller, customer, full body, hands.
- "Snapshot for Claude" writes `current_view.png/json` in the lab folder so Claude sees exactly the user's view.
- Rebuild data: `build/lab_build.py` in Blender 5.1 (~20 s): Boss FBX + Anim_Idle.fbx retarget (parent-space copy, checked against the source), face npz -> `data/boss.glb`, `data/scene.bin/json`.
- Next: body movement / gestures (pointing) and village movement on top of this.

## Dialogue Lab: emotion slider, lights, settings, ankle, procedural body (Nov 6)
- Emotion slider: overlay baked at gains 0/0.3/0.6/1/1.3/1.6/2 (1.6 = approved, exact), expressed in the A5 PCA basis (max 0.36 mm), blended live. Above 1.6 the per-event cap grows with the gain.
- Light sliders, foldable panel sections; all settings persist in `Labs/DialogueLab/settings.json` (server endpoint), not just browser storage.
- Left ankle fix: Boss `foot_l` rest frame is twisted ~24 deg vs the mannequin (foot_r 6 deg, rest symmetric); lab retarget copies that bone as a delta from rest (sole tilt 5 -> 0.7 deg). Probably worth the same treatment in UE if it shows up there.
- Procedural body layer `body.js` (user: everything procedural, no licences, no per-scene regeneration; believable over word-accurate): breathing + inhale before phrases, weight shifts with leg IK, posture shifts at ~1/3 of turn starts, speaker gesture units on stressed words (offer, open palms, beat, shrug, wave-off, chest, point at partner's chest from chest height, thumb+index "two" on *dos*), listener self-touch (chin, hip, clasped hands, neck, nose) chosen by mood; energy/size follow emotions and the Emotion slider. Deterministic per character.
- Research notes (Nov 6): neural gesture models (ZeroEGGS, EMAGE/BEAT2, LiveGesture) are non-commercial licences -> not usable; GENEA 2023: generated gestures far below mocap on speech-appropriateness; game practice (Witcher 3) = tagged library + additive/masked layers + generator from voice.

## Dialogue Lab checkpoint (Nov 6, 08:13) - `Labs/DialogueLab/checkpoints/2026-11-06_nods4`
- Procedural body layer removed (user: "horrendous"); replaced by the user's speech poses (`speech poses.fbx`, frame 4 dropped via `--poses-skip 4`): Pose 1-6 (explanatory/emphasis), Shrug (frame 9), Plead (frame 10); fingers stay on the idle.
- Motion tab: per-pose profiles = [min, max] ranges for blend in/out (duration + bezier ease in/out), hold (may be negative), idle sway, strength; ONE variation value u per take drives all ranges (coherent); preview plays on both characters; Save / Save as new; changing pose keeps ranges unless the pose has a saved profile. 8 profiles saved in `motions.json`.
- On the dialogue (`speech.js`): ~half the phrases get a gesture, apex on the stressed word, pose from the script emotion; explanatory poses chain 50% into another explanatory pose of the SAME arm (pose -> pose, no idle in between). 9 gestures + 2 chained in the apples scene.
- Listener nods: native Unreal inner-voice nods amplified only in the quick pitch band while listening; user keeps 4x. Settings (emotion 1.3, lights, nods, panel width...) persist in `settings.json`.

## Seller accent fix: French-accent ladder for eleven_v4 (Nov 6, overnight, cloud Claude)
- Problem: Seller (Marcel_FR) lines 00/02/04 of the apples scene read as Spanish/Italian (Whisper-small language ID French 0.01/0.11/0.12; line 06 and all Customer lines 0.95+). It is the TEXT, not the voice: Sarah_FR reading line 00 also comes out Spanish (0.04). eleven_v4 picks the language from the spelling; Occitan is a supported language, so "Pomas frescas" gets spoken as fluent Occitan, which sounds Iberian/Italian.
- Tested (Seller, 130 takes, 5.1k credits; 22.5k left): French primer sentence + trim (worse, 0.0-0.24 on line 00), previous_text, language_code fr (ignored by v4), stability 0.8 / similarity 1.0, all lines in one request, the tag repeated, 8 accent-tag wordings, 3 spellings.
- What works: a *southern* accent tag `[thick French accent from the south of France]` (the plain/strong/thick "French accent" tags do much less), plus spelling the Occitan words the French way when needed:
  - L0 classical spelling: ~50% of Seller lines read as French (>= 0.90)
  - L1 French-looking spelling, final -a -> -o (`Tools/Speech/occ_frspell.py`): ~80%
  - L2 French-looking spelling with mute -e: 11/11, but the closest to plain French
- Pipeline: `accent_ladder.py <batch> --level 1` -> `el_accent.py` -> score with `accent_eval.py` (Whisper-small LID, French >= 0.90 on the whole line) -> regenerate only the failures at L2. About 1.2x the credits of a single pass, never 3x. Validated on 8 new Seller lines: L1 7/8, L2 8/8.
- Apples scene: `Saved/Speech/ab_apples_occ_fv_accentfix/` (v4 = scene to use, orig = approved takes for A/B, index.html). Replaced lines come from takes already made during the experiments:
  - 00: L1 (seed 9), French 0.94, 4.48 s (was 4.80 s)
  - 02: L0 (seed 77), 0.99, 5.44 s (was 5.28 s)
  - 04: L0 (seed 77), 0.96, 4.88 s (was 5.04 s)
  - The other lines are unchanged.
- Not done, waiting for the user's ear and go:
  - face solve for the 3 new lines;
  - scene timing;
  - lab data.


## Dialogue Lab: scenarios + live gaze (Nov 6 evening, cloud Claude)
- Big tabs Standing / Walk / Sit. Standing: opening slider (0 = face to face, 110 = the old layout) + distance. Walk: side by side, in place (M_Neutral_Walk_Loop_F, root motion stripped) + spacing. Sit: Seller on `slashes/recoveries/sitting.fbx` (a ground sit, pelvis 0.11 m, so no stool), Customer standing around him (angle 0-120 deg from his forward + distance).
- `lab_build.py --clip <Name> <fbx>` (repeatable) retargets extra body clips onto muted NLA tracks; export_frame_range off so each clip keeps its own length. Backup of the previous data in `build/backup_*_before_scenarios`.
- Live gaze (`gaze.js` + app.js), layout independent, nothing baked: the eyeballs' baked PCA motion is dropped (mean shape kept) and each eyeball is rotated in the vertex shader about its own centre (bind space, after morphs, before skinning); optical axis = vertex at eye UV (0.5, 0.5). Target plan per scenario from the research: speaker looks away at turn start (back ~0.7 s in), on the partner for the last second, floor-holding glances at phrase ends; listener ~on the speaker with short downward breaks; walking: path ahead, glances at phrase/turn ends, scans. Head takes 0.6 of the turn (critically damped spring), eyes the rest (limits 30 yaw / 22 up / 26 down), closed loop pushes head then upper spine (spine_04/05) when the eyes hit their limit. Angles measured from the animated head (works with the slumped sit pose). Eye error <1 deg standing/walking; seated looking straight up at the partner ~5-7 deg short (neck + spine at their limits).
- Not done: eyelid follow (lids keep their baked shapes), Unreal side (look morphs for the game).


## Dialogue Lab: gaze refinements after the user's review (Nov 6 late)
- Hand hitch (standing ~F123/142): a chained gesture dropped to 0 in 1 ms when the next pose arrived; with a profile strength < 1 the next pose doesn't fully cover it. Now it fades out over 0.35 s after the next one arrives (speech.js). No hand acceleration spikes left over the scene.
- Gaze plan (gaze.js) rewritten: base attention track = partner blocks (1.5-3.5 s speaking, 2.5-5.5 s listening) alternating with neck relief every ~4.5-8 s (rest = neutral head + eyes ahead slightly down, soft = eyes on the partner with the head mostly relaxed, between = 35-70 % of the way from neutral to the partner); conversation events on top (turn-start look-away 0.7-1.2 s, phrase-end look-aways, turn-end on the partner, listener glances down 0.7-1.2 s, new speaker draws the eyes); overlays of the same kind < 1.2 s apart merge, any gap < 0.6 s is bridged (no double looks).
- Walk: glance windows merged when < 2 s apart (no double look), capped 2.6 s, 55 % full look / 25 % eyes-only (head relaxed) / 20 % half-way; look-arounds (sideways or the ground ahead) only in clear gaps: never within 1.6 s after a glance or 1 s before one.
- Healthy limits: neck yaw 50, up 28, down 35; upper back adds yaw 20 / up 10 / down 15; eyes 30 / 22 up / 26 down. The gaze turn bends mostly the lower neck (neck_01 .38, neck_02 .37, head .25; the baked head motion keeps its own split). Head spring slower (omega 6, torso 4). The closed loop that pushes the head when the eyes hit their limit is off for 'soft' / 'rest' and capped at 30 deg.
- Neck fatigue: a continuous look at the partner that needs a strongly turned head relaxes it (head share down to 40 % after ~1.5-4 s, eyes keep the partner). Head yaw follow 0.5 standing / sitting. Measured over the scene: longest hold of the head > 30 deg 3.5-4.6 s standing, ~7 s for the Seller sitting on the ground (the Customer stands 75 deg to his side and above him), 2.5 s walking.


## Dialogue Lab: neck shape, calm sitting, Group tab (Nov 6 night)
- Neck: the gaze pitch now mostly straightens the lower neck (neck_01 .52, neck_02 .32, head .16; yaw .36/.34/.30) so a slumped sitter looking up lifts his neck instead of folding the head back on a bent neck (user sketch). Sitting allows 36 deg neck extension (the clip's neck starts bent forward).
- Neck breaks checkbox (off = no relief looks, no relaxing of a held turned head).
- Sit: "Calmer when sitting" (default on): the seated character's gestures and baked head motion at half.
- Group tab (3 or 4 people, spread slider), horseshoe open to the camera. Bystanders B3/B4 are extra Boss copies with no face track of their own: they wear the face of whichever speaker is listening at that moment (closed mouth, blinks, listener reactions), 0.35 / 0.7 s later. Gaze from the research: Vertegaal et al. CHI 2001 (4-person: listeners look ~7x more at the speaker, 62 % vs 8.5 %; speakers ~3x more at the addressee, 40 % vs 12 %, but every listener gets glances), Holler & Kendrick 2015 (unaddressed listeners shift to the next speaker ~0.25 s before the turn ends in ~3/4 of cases). Implemented: speakers mostly on each other + inclusion glances to bystanders at phrase ends (45 %), listening speaker glances at a bystander now and then; bystanders on the current speaker (~80 %), anticipate the next speaker before the turn ends (75 %), glance at another listener now and then (35 % every 5-8 s).
- Next for the group: a real multi-speaker script (new lines, voices, face solves) so the bystanders can talk.


## Dialogue Lab: neck twist + seated gesture slider (Nov 7)
- Each neck bone now turns about its own length (60 %, blended with the vertical; the head about its own up) instead of the world vertical: on the slumped sitting neck the old vertical turn swung the head sideways like a crane with no twist in the neck (user). Gaze angles are still measured in the world frame (yaw about the vertical, pitch = elevation), which splits a head looking at the ground correctly.
- Sit: "Gesture amplitude (seated)" slider (default 50 %), gestures only; the head motion and listener nods are no longer scaled.


## Dialogue Lab (Nov 7, 1:30): sit neck range, no head shaking, arrow keys
- Sitting neck range up 50 / yaw 65 (head stops at the limit, eyes do the rest); the seated Seller now reaches the Customer's face at 75 deg.
- Gaze plan is resolved into one cleaned sequence of looks: no look under 0.7 s, and a short look at someone else (< 1.6 s) between two looks at the same person is dropped (the group speaker's bystander -> listener -> bystander "shaking no"). Measured: no head yaw reversal > 12 deg within 1.6 s for any of the 4 people in Group.
- Arrow keys: tap = one frame, hold = scrub at 1x after 0.12 s (no OS key-repeat delay); left = back.

