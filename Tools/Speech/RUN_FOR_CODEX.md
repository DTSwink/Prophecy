# Run the speech mockup (for Codex)

From the project root (spends about 1,400 ElevenLabs characters; the script refuses batches over 3,000):

```powershell
& 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Tools/Speech/el_generate.py Tools/Speech/batches/mockup1_gate.json
```

- The key is read from `ELEVENLABS_API_KEY` (process env, else the Windows user environment). Never print it.
- Output: `Saved/Speech/mockup1_gate/` (git-ignored). Open `index.html` there to listen ("Play scene" per model).
- Report the console output (per-line status, credits used/left). Do not commit the Saved folder.
