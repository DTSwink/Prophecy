@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
cl /nologo /EHsc /std:c++17 /I StandaloneSim/sim_core/include Saved/Diagnostics/TestRootFacingTurns.cpp /Fe:Saved/Diagnostics/TestRootFacingTurns.exe /Fo:Saved/Diagnostics/TestRootFacingTurns.obj
if errorlevel 1 exit /b 1
Saved\Diagnostics\TestRootFacingTurns.exe

