# Speech corpus v1 (built overnight, Nov 4)

Gibberish dialogue bank for Prophecy characters: real dialogue structure + context emotions, translated into the
French-flavoured invented language. The English is only the "trame de fond" (meaning/emotion scaffold) and is never spoken.

## Files
| file | what |
|---|---|
| `Saved/Speech/corpus/speech_corpus_v1.jsonl.gz` | full pool: 8,228 scenes / 71,905 lines (~4.2M characters; far more than we will ever voice) |
| `Tools/Speech/corpus/starter_bank_v1.json` | balanced pick: 81 scenes / 635 lines / ~30.8k characters (~34 min), fits one month of credits |
| `Tools/Speech/corpus/PREVIEW.md` | 9 scenes side by side (speaker, tags, text, meaning) |
| `Tools/Speech/lexicon_v2.json.gz` | the language's memory: English lemma -> root sounds, names. Keep it: same word = same root forever |
| `Saved/Speech/corpus/forms_v2.json.gz` | every spelled word form -> sound spans (for mouth shapes); rebuildable from the lexicon |
| `Tools/Speech/lang2.py` | grammar layer (needs `lang.py`) |
| `Tools/Speech/corpus/*.py` | collect -> annotate -> build -> select pipeline (cloud paths) |

## Scene record
`id, source, ref, category, energy (low/medium/high), n_speakers, speakers[{id, name_en, name, gender}],
lines[{spk, en, emotion, labelled, intensity 0-3, tags, text}]`. `name` is the invented name; `gender` is m/f/u
(u = unknown, cast freely). `energy` is meant for voice settings (e.g. lower stability for high-energy scenes).

## Sources (pool)
| source | scenes | what it gives |
|---|---|---|
| Original (written for Prophecy) | 25 | market haggling, mercenary pay, tavern tales, grandmother story, gate guard dispute, inheritance fight, village/camp small talk, grief, injury, birth |
| MELD (declare-lab, GPL-3.0) | 1,338 | multi-party TV dialogue, every line emotion-labelled |
| Friends transcripts (emorynlp character-mining) | 4,189 | multi-party everyday scenes, part emotion-labelled |
| CRD3 (Critical Role D&D, CC BY-SA 4.0) | 2,226 | fantasy storytelling, game master narration + players (dice/rules talk filtered out) |
| Deal or No Deal (Facebook, CC BY-NC) | 450 | two-party bargaining |
Speakers per scene: 2 = 3,038, 3 = 3,472, 4 = 1,743 (pool). Categories: small talk 4,207, storytelling 1,647,
emotional 756, dispute 665, banter 478, bargaining 450 (+ originals).

## Emotion tags (watered down on purpose)
- 81% of lines have NO tag. Neutral lines are never tagged; about half the mild lines in calm scenes drop their tag.
- Intensity is capped by category: small talk / storytelling / bargaining 1 (storytelling peaks 2), banter and
  emotional 2, dispute 3. Shouting only exists in disputes (281 lines in the whole pool).
- Mild tags: warmly, amused, cheerfully, curious, softly, wistful, hesitant, annoyed, calmly, gently, confident,
  dismissive, chuckles. Medium: excited, happily, surprised, sad, nervous, worried, angry, frustrated, firmly, laughs.
  Strong: shouts, panicked, gasps, sorrowful.
- Labels come from the datasets where present (MELD all lines, Friends partly); otherwise from text cues, which can
  never reach the strongest level.

## Grammar (lang2) — why it sounds like a language, not a cipher
- Same English lemma -> same root (run/ran/running share one), so words recur naturally; common English words get
  short roots, rare words long ones (Zipf).
- Endings: plural -i, past -ette, -ing -an, -ly -man (French -ment feel), comparative -on; 3rd-person present silent.
- French word order for adjectives (after the noun, except beauty/age/number/goodness/size ones, which stay before).
- Negation circumfix like ne...pas: `zou` before the verb, `teu` after it. English "do" is dropped.
- Elision: dè/ké/jé/vé + vowel -> d' / k' / j' / v'. Interjections: euh, ouah, hé, aïe, oups; yes vèl, no nèk,
  okay tavé, please pliza, thanks mérsil, sorry dézou, hello bénou, bye kazé.
- Names are consistent everywhere (a character mentioned in a line has the same invented name as the speaker).
- Checks: no English function words left in any line; 4 lines are pure punctuation ("..." / "?") from the source.

## Cost reality
Full pool ~4.2M characters = ~47 months of the Starter plan. Plan: voice the starter bank first (~30.8k chars),
listen, tune tags/voices, then pick more by category from the pool. A scene's cost = sum of (tags + text) characters.
