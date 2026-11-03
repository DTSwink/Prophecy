@echo off
rem Runs MetaSounds with the Python environment that Sound Studio already installed.
set "PY=%USERPROFILE%\Documents\Unreal Projects\Prophecy\Saved\SoundStudio\env\Scripts\pythonw.exe"
if not exist "%PY%" (
  echo Sound Studio's Python environment was not found at:
  echo %PY%
  pause
  exit /b 1
)
start "" "%PY%" "%~dp0metasounds_app.py"
