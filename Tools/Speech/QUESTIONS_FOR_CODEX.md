# ElevenLabs questions for Codex (from the cloud Claude session, Nov 4)

Context: we're building pre-recorded gibberish speech for Prophecy characters. The cloud session can't
reach api.elevenlabs.io (its network policy blocks it), so generation will run on this laptop.
Please answer in `Tools/Speech/ANSWERS.md` (create it). **Never write the API key into any file or chat.**

## A. Run the probe (answers most questions automatically)

1. Is an ElevenLabs API key available on this machine? Check for the env var `ELEVENLABS_API_KEY`
   (report only present/absent). If absent, ask the user to set it as a **user environment variable**
   (`[Environment]::SetEnvironmentVariable('ELEVENLABS_API_KEY','<key>','User')`) and do not handle the key text yourself.
2. From the project root, run:
   `& 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Tools/Speech/elevenlabs_probe.py`
   It uses ~300-600 credit characters and writes `Saved/Speech/probe/` (summary.json, a few small mp3 + timing json).
   Do not commit that folder. Report the console output and whether `summary.json` has errors.
   Optional: set `$env:PROBE_VOICE_ID` first if the user names a voice to test.

## B. Things the probe can't answer

3. Does this machine have **ffmpeg** on PATH (`ffmpeg -version`)? Not required, just useful.
4. Is a Python with `pip` usable here besides the stepper python310 (in case we want the official `elevenlabs`
   package)? Not required; the probe is stdlib-only.
5. If the API key is a **scoped/restricted** key, which permissions does it have? Needed: Text to Speech,
   Voices (read), Models (read), User (read). (The probe errors will also show this.)

## C. Questions for the user (just copy their answers)

6. Which voices do you want: existing ElevenLabs library voices, your own designed/cloned voices, or should I
   pick candidates? How many distinct voices (Boss, enemies, allies, crowd)?
7. Is it OK to spend roughly **25-30k characters per voice** for a ~30 minute bank (~150-300 lines)? Start
   smaller (e.g. 5k characters, ~5 min) for a first listen?
8. Moods per voice: calm / angry / scared / hurt / battle shout — anything to add or drop?
9. Does your ElevenLabs plan allow **commercial use** of generated audio (paid tiers do; free does not)?
