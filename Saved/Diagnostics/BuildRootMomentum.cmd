@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
cl /nologo /EHsc /std:c++17 /I StandaloneSim/sim_core/include Tools/NN/TestProphecyRootMomentum.cpp /Fe:Saved/Diagnostics/TestRootMomentum.exe /Fo:Saved/Diagnostics/TestRootMomentum.obj
if errorlevel 1 exit /b 1
Saved\Diagnostics\TestRootMomentum.exe
