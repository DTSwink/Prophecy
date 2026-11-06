# Invented speech language (French-flavoured) — v1, seed 7

Purpose: believable but meaningless chatter for Prophecy characters, read by ElevenLabs.
Generator: `Tools/Speech/lang.py` (cloud; Python + `wordfreq` for the real-word filter). Lexicon dump: `lexicon_seed7.json`.

## How it was designed (research summary)
- Sounds first, words later (Rosenfelder, *Language Construction Kit*); uneven, power-law sound frequencies,
  never uniform (zompist word-generator guidance).
- French feel from French statistics: syllable shapes weighted like spoken French (Wioland 1985: CV 56%,
  CCV 14%, CVC 14%, V 10%, so ~80% open syllables); uvular R, l, s, t most common; nasal vowels an/on/in;
  front rounded u / eu; no diphthongs; pronounced final consonants written with a final -e as French does.
- Own identity: frequent short function words with k / z / j / v onsets (za, dè, zi, vé, ké, jé...), a nod to
  Magma's Kobaïan, so it is French-sounding but not French.
- Recurring endings (-on, -ère, -u, -ance, -ige, -eau, -in, -al) and prefixes (re-, dé-, a-) make words feel related.
- Real words rejected: every root is checked against French/English/Spanish/Italian frequency lists; function
  words are checked by SOUND against common French function words (de, la, les, des, qui, que, vous, quand...).
- Scenes are written in English for meaning and emotion, then relexified word-by-word and consistently
  (same English word -> same invented word), so repetition and sentence rhythm look like a real language.
  Punctuation, CAPS emphasis and ElevenLabs [tags] are kept. Proper names become capitalised invented words.
- Every invented word keeps its sound-to-letter spans, so ElevenLabs' per-character timing gives exact mouth
  shapes later.

## Function words
| word | English group |
|---|---|
| za | the, a, an |
| dè | of, from |
| zi | and |
| vé | to, into, toward, towards |
| ké | in, on, at |
| jé | is, are, am, be, was, were |
| pè | i, me |
| bé | you |
| fè | he, him, she, her, it |
| ju | we, us |
| kon | they, them |
| zou | not, n't, no |
| meu | that, this, those, these |
| leu | my, mine |
| zan | your, yours |
| pon | his, its, their, our |
| lan | what, which |
| bou | where, there, here |
| kou | with |
| jou | for |
| mio | will, shall, would, do, does, did, have, has, had |
| lia | then, so |