
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
