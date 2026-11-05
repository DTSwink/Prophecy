# How to work with Unreal in this project (without the editor)

This is how the noose and gallows work was done: everything ran headless from scripts, with no clicking in the editor. The laptop is shared by other agents and has little RAM, so the rules below matter as much as the commands.

## 1. The job runner (`Saved/ClaudeJobs`)

- `runner.ps1` (start it with `StartRunner.cmd`) watches `Saved/ClaudeJobs/inbox/` every 2 s.
  - Drop a `*.ps1` file in the inbox. It runs hidden in its own PowerShell process.
  - Its output goes to `outbox/<job>.log`. When it finishes, `outbox/<job>.done` holds the exit code.
  - Jobs run **in parallel**. Two jobs that both build or both launch Unreal will fight, so every job must check for the others (see the template).
- `heartbeat.txt` shows the runner's last tick and PID. If it is stale, the runner is down.
- The log is written in chunks. A log that hasn't changed for a minute does **not** mean the job is hung. Before you conclude anything, check the game's own log (`Saved/SceneTest/<run>/game.log` ends with `Log file closed`) and the folder's file times. Killing a "hung" job that was actually rendering costs a whole run.

## 2. Job template (build one C++ change, run a test, make a video)

Copy an existing job, for example `Saved/ClaudeJobs/running/job225_noose_v22.ps1` (the runner moves each job there once it starts) and change only the stage folder and the run list. It does these steps in order:

1. **Stage, don't edit in place.** Put your changed files in `Saved/ClaudeJobs/<topic>/src_vNN/...`. The job copies them into `Source/GameAnimationSample3/...`.
2. **Source guard.** Hash each module file and refuse to run (exit 5) unless it matches a version you staged before. If someone else edited the file, you'd silently overwrite their work.
   - Every new version must add the previous stage folder to `$known`.
   - If a build fails, the module now holds the broken file, so the next stage folder must be in `$known` too.
3. **Wait for room:** up to 2 h for ≥ 3 GB free RAM, and for **no other Unreal process on this project** (editor, commandlet or `-game`). A build beside a running editor fails on the locked DLL.
4. **Close the editor safely** only if it's open: `Tools/RunUnrealRemote.py` + `beetools/close_editor_safe.py`. Give up (exit 3) if it won't close, because the user may have unsaved work. Reopen it at the end **only if this job closed it**.
5. **Build:** `Engine/Build/BatchFiles/Build.bat GameAnimationSample3Editor Win64 Development -Project=... -WaitMutex -FromMsBuild -MaxParallelActions=2`.
   - Filter the output for `error|warning C|Result`.
   - On failure, stop and leave the editor closed, so it doesn't launch with a stale DLL.
6. **Run headless tests:** `UnrealEditor.exe <uproject> <map> -game -RenderOffscreen -unattended -windowed -ResX=1280 -ResY=720 -NoSound -nosplash -fps=60 -SceneTest=<script> -SceneTestOut=<dir> -abslog=<dir>/game.log`.
   - Wait for ≥ 3.5 GB free before each run.
   - Kill the run if free RAM drops below 150 MB, or after 25 min.
   - Extra cvars go in `-dpcvars=a=1,b=2`. Your own test switches go on the command line, read with `FParse::Value(FCommandLine::Get(), ...)`.
7. **Video:** ffmpeg turns `<dir>/frame_%05d.jpg` into an mp4 (`-framerate 30 -c:v libx264 -crf 20`).
8. **Report:** grep `game.log` for your own log lines plus `Error:|Ensure|Fatal|Assertion`, and print them into the job log.

## 3. Scene-test scripts (`-SceneTest=`)

Plain text, one timed command per line (see `Saved/ClaudeJobs/gallows/hang_neck7.txt`):

```
anchor A_Potence            # actor the scene is relative to
hold Dummy                  # keep the dummy kinematic until released
record 0 27 2               # capture frames 0-27 s (every 2nd tick)
cam 0  196 -470 160  196 0 150  55   # fixed camera: position, look-at, FOV
orbit 4.4 9.4 115 14 45     # close orbit around the focus between 4.4 and 9.4 s
tie 5.0 Dummy neck_02 - 0   # call into game code at t = 5 s
reelby 10 13 0.18           # animate a parameter over a time window
shot 15 hanging_neck        # still image
exit 27
```

Make the game code log one diagnostic line about twice a second. Measure numbers in the log (stretch, error, speed) rather than guessing them from the picture.

## 4. Work off-Unreal first

Unreal runs are slow (~1.5 min build, ~1.5 min per test) and heavy on a shared laptop. Do the thinking elsewhere:

- **Physics:** `Saved/ClaudeJobs/joltlab/lab.cpp` is a standalone Jolt build of the same rope and mannequin rigs. A run takes 2 s, you can test 5 variants in parallel, and it writes metrics to CSV. It builds with `build_lab.sh` (g++, Linux) against the same Jolt version the plugin uses. Reproduce the bug there, find the fix, then make **one** Unreal run to confirm. Example: the neck stretching while reeling was 6 cm in UE and 5.4 cm in the lab. The lab found the cause and the fix, and UE runs then only confirmed it and set the final strength.
- **Engine behaviour:** before guessing how an engine API works, copy the real source out with a read-only job (`Copy-Item` from `C:/Program Files/Epic Games/UE_5.7/Engine/...` into the outbox) and read it.
- **A/B in one job:** put 2 or 3 runs with different switches in one job, so they share one build.

## 5. Look at the result properly

- Always make the video and **look at it at full resolution**: crop the area that matters, line up before/after at the same timestamps, check the first seconds and every transition.
- Check that the mp4 is fresh (size and mtime newer than the job start). A previous run's file in the same folder looks the same.
- Watch for: double objects, black or NaN shading, popping, stretching, things passing through each other.

## 6. Pitfalls we hit

| Symptom | Cause / fix |
|---|---|
| A file copied to the machine has old contents | Copy, then read it back and compare the hash. If it's stale, copy again under a new source file name. |
| Runtime morph renders black | The plain GPU-skin path breaks external morph sets. They only render right through the GPU skin cache: set `SkinCacheUsage` on that component. |
| Something re-shows a component you hid every frame | A Blueprint calls `SetVisibility(true)`. Use `SetHiddenInGame` instead; the Blueprint doesn't touch that. |
| A body hanging on a joint stretches when the rope's length changes | Jolt fixes a moving limit only with position corrections. Feed the motion forward as impulses on the whole body. Never overwrite a body's velocity: this is a realistic sim, so add to it only. |
| Velocity added from game code piles up | Several frames can fall within one physics step, so you read the same state again. Apply at most once per step: skip if the body's position hasn't changed. |
| `UpdateJoint` makes a joint briefly weak | It resets warm starting. Don't call it every frame; update only when the change is large enough. |

## 7. Manners

- One job at a time from you, and keep it small (only `-MaxParallelActions=2`).
- Never leave the editor in a different state than you found it.
- Don't edit shared files that other agents own. If you must, keep the source guard on and say so.
