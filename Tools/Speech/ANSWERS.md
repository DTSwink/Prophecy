# ElevenLabs probe answers

Checked locally on November 4, 2026 (Europe/Warsaw), following `QUESTIONS_FOR_CODEX.md`.

## A. Probe

### 1. API key availability

- Windows user environment: **present**, verified after the user completed private setup.
- The key was passed to the probe's process environment without displaying it or writing it to a file.

The earlier absent-key result is superseded by this successful authenticated run.

### 2. Probe execution and errors

Ran the requested probe from the project root, loading the existing user environment variable into that process:

```powershell
$env:ELEVENLABS_API_KEY = [Environment]::GetEnvironmentVariable('ELEVENLABS_API_KEY', 'User')
& 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Tools/Speech/elevenlabs_probe.py
```

Console output:

```text
eleven_multilingual_v2 calm 200
eleven_v3 calm 200
eleven_v3 angry_tag 200
eleven_flash_v2_5 calm 200
PROBE_DONE -> C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\Speech\probe\summary.json
```

**All four synthesis tests succeeded**, with MP3 audio and character timing alignment. Models and voices endpoints both returned HTTP 200; 21 voices were returned. The script automatically selected **Roger - Laid-Back, Casual, Resonant**, voice ID `CwhRBWXzGAHq8TQ4Fs17`, solely as the capability-test voice, not as a production voice decision.

| Model | Test | Submitted characters | Audio bytes | Last alignment end (seconds) |
|---|---|---:|---:|---:|
| eleven_multilingual_v2 | calm | 68 | 88650 | 5.48 |
| eleven_v3 | calm | 68 | 95755 | 5.92 |
| eleven_v3 | angry_tag | 54 | 80291 | 4.96 |
| eleven_flash_v2_5 | calm | 68 | 117071 | 7.245 |

258 text characters were submitted across the four successful synthesis calls. Actual billed credits were not verified; character count is not a billing receipt. HTTP/alignment success does not establish listening quality or emotion accuracy.

The initial subscription request lacked `user_read`. After the user updated permissions, a subscription-only retry returned **HTTP 200** on November 4, 2026. The summary now contains **no errors**. No synthesis was repeated or generation credits spent on this retry.

Current subscription response:

```json
{
  "tier": "starter",
  "status": "active",
  "character_count": 53426,
  "character_limit": 90000,
  "next_character_count_reset_unix": 1795284918,
  "can_use_instant_voice_cloning": true,
  "can_use_professional_voice_cloning": false,
  "voice_limit": 10,
  "professional_voice_limit": 0
}
```

The output directory contains the summary and four MP3/timing-JSON pairs. Its Git ignore status was confirmed earlier. Nothing was staged or committed.

## B. Local tooling and permissions

### 3. FFmpeg

**Available on PATH.** `ffmpeg -version` succeeded:

```text
ffmpeg version 8.1.1-full_build-www.gyan.dev
built with gcc 15.2.0 (Rev13, Built by MSYS2 project)
```

### 4. Another Python with pip

**Yes.** The Unreal installation includes a separate Python:

```text
C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/ThirdParty/Python3/Win64/python.exe
Python 3.11.8
pip 24.0 (python 3.11)
```

Both `--version` and `-m pip --version` succeeded. No packages were installed and the Unreal environment was not changed. If this interpreter is used for the speech tooling, create a separate speech virtual environment rather than installing into Unreal's Python.

The existing `Saved/SoundStudio/env/Scripts/python.exe` also has working pip 23.0.1, but it is a Python 3.10 virtual environment based on the stepper installation, not a separate base interpreter. It was only inspected and should remain dedicated to Sound Studio.

`py -0p` lists only the stepper Python 3.10 installation; the Unreal interpreter was verified directly.

### 5. API key permissions

Observed access:

- Text to Speech: **working** (four HTTP 200 responses).
- Voices read: **working** (HTTP 200).
- Models read: **working** (HTTP 200).
- User read: **working** after the user updated permissions; subscription-only retry returned HTTP 200.

Other scopes, key credit limits and expiry were not inspected. No permissions were changed by Codex.

## C. User decisions — received November 4, 2026

The following are the user's answers, copied verbatim. Unspecified details remain undecided.

### 6. Voices and roles

> candidates

Candidates should be proposed. Voice count and role allocation were not specified.

### 7. Bank size / budget

> we'll see about that later

Production-bank size and spending are deferred. No 5k or 25–30k per-voice budget has been approved; the small requested capability probe is separate.

### 8. Moods

> we'll actually take real dialogues with different number of protagonist and we'll pull emotion from there , we'll only do speech emotion the battle shout are handled separately

Use dialogue context with varying participant counts to derive speech emotions, rather than treating the proposed five moods as a confirmed list. Battle shouts are outside this speech workflow.

### 9. Commercial-use eligibility

> yes permits it

Commercial use is confirmed by the user. The subscription API now reports the account tier recorded in section A; commercial-use eligibility remains the user's confirmation, not a separate legal review.

## API setup follow-up

The user requested help instead of PowerShell commands. `setup_api_key.ps1` provides a local masked-input window that saves the key directly as the user's `ELEVENLABS_API_KEY` environment variable. It does not print it, write a key file, or send it through chat. The user must create/copy the key in their own account and paste it into that window. The user completed this setup. Codex verified presence only and then ran the small capability probe documented above. No account key was created by Codex; no production-bank generation was performed.
